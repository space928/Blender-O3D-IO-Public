# ==============================================================================
#  Copyright (c) 2022-2023 Thomas Mathieson.
# ==============================================================================
import os

import bpy
from . import o3d_node_shader_utils
from .blender_texture_io import load_texture_into_new_slot, find_image_path
from .o3d_cfg_parser import read_generic_cfg_file
from mathutils import Vector
import mathutils

import numpy as np
import math


def log(*args):
    print("[OMSI_Spline_Import]", *args)


def frac(x):
    return x - math.floor(x)


def clamp(x, _min, _max):
    return max(min(x, _max), _min)


class Spline:
    def __init__(self, sli_path, spline_id, next_id, prev_id,
                 pos, rot, length, radius,
                 start_grad, end_grad, use_delta_height, delta_height,
                 cant_start, cant_end, skew_start, skew_end,
                 mirror, local_id):
        self.sli_path = sli_path
        self.id = spline_id
        self.next_id = next_id
        self.prev_id = prev_id
        self.pos = pos
        self.rot = rot
        self.length = length
        self.radius = radius
        self.start_grad = start_grad
        self.end_grad = end_grad
        self.use_delta_height = use_delta_height
        self.delta_height = delta_height
        self.cant_start = cant_start
        self.cant_end = cant_end
        self.skew_start = skew_start
        self.skew_end = skew_end
        self.mirror = mirror
        self.local_id = local_id

    def __str__(self) -> str:
        return "Spline {0}: sli_path = {1}; id = {2}; next_id = {3}; " \
               "prev_id = {4}; pos = {5}; rot = {6}; length = {7}; " \
               "radius = {8}; start_grad = {9}; end_grad = {10}; " \
               "cant_start = {11}; cant_end = {12}; skew_start = {13}; " \
               "skew_end = {14}; mirror = {15}. ".format(self.id, self.sli_path, self.id, self.next_id,
                                                         self.prev_id, self.pos, self.rot, self.length,
                                                         self.radius, self.start_grad, self.end_grad,
                                                         self.cant_start, self.cant_end, self.skew_start,
                                                         self.skew_end, self.mirror)

    def _compute_spline_gradient_coeffs(self):
        """
        Computes the hermite spline coefficients for this spline from the gradient and delta height properties.
        :return: the coefficients c, a, and b representing the z^3, z^2, and z terms respectively
        """
        b = self.start_grad/100
        if self.use_delta_height:
            c = (self.end_grad-self.start_grad)/100 * self.length - 2 * (self.delta_height - self.start_grad/100 * self.length)
            c /= self.length * self.length * self.length
            a = -(self.end_grad-self.start_grad)/100 * self.length + 3 * (self.delta_height - self.start_grad/100 * self.length)
            a /= self.length * self.length
        else:
            c = 0
            a = (self.end_grad-self.start_grad)/100/(2*self.length)

        return c, a, b

    def generate_tesselation_points(self, spline_tess_dist, spline_curve_sag):
        """
        Generates a set of z coordinates along the spline which represents an "ideal" sampling of the spline.

        :param spline_tess_dist:
        :param spline_curve_sag:
        :return:
        """
        """
        This is a non-trivial problem to solve, and hence the answer is somewhat approximate here. Our spline is 
        essentially a hermite curve along the y axis and an arc along the xz plane. For ease of implementation we 
        consider the sampling of these separately and then merge and weld the samplings together.
        
        The Y axis can be described by the following function: 
        (see https://www.desmos.com/calculator/7xfjwmqtpz for my calculator)
            f_y(z, x) = z^3*c + z^2*a + z*b + x*(z*cant_delta + cant_0) {0 <= z <= length}
        To approximate the curvature of the spline we take the arctangent of the first derivative (essentially 
        converting the gradient of the function into an angle):
            f_dy(z, x) = 3z^2*c + 2z*a + b + x*cant_delta {0 <= z <= length}
            f_curvature(z, x) = abs(atan(f_dy(z, x))) * (1 + 1/r)
        We want to sample this at regular horizontal slices of the curvature equation (ie the higher the gradient of 
        the curvature equation the more samples to generate), we do this by taking the inverse of the curvature equation 
        and sampling it at regular intervals along the x axis. This is represented by the following expression:
            f_icurvature(z, x) = (-a +- sqrt(a^2 - 3c(b + x*cant_delta) +- 3c*tan(z)) / 3c {0 <= z <= pi/2}
        Because of the two +- operations in the above equation, we can actually get up to four points per iteration.
        """
        samples = []
        n_grad_samples = 0
        if self.start_grad != self.end_grad or self.use_delta_height:
            c, a, b = self._compute_spline_gradient_coeffs()
            if a != 0 or c != 0:
                cant_delta = (self.cant_end - self.cant_start) / self.length / 100
                # Maybe we should consider the value of x?
                x = 0
                _3c = c*3
                if self.use_delta_height:
                    a23cbxc = a*a - _3c*(b + x * cant_delta)
                else:
                    bxc2a = (-b - x * cant_delta)/(2*a)
                z = 0
                if (math.pi/2) / spline_curve_sag > 10000:
                    log("[ERROR] Spline tesselation would take too long, please increase the spline curve sag distance!")
                    # Return a basic tesselation...
                    n_segments = min(max(math.ceil(self.length / spline_tess_dist), 1), 100)
                    dx = self.length / n_segments
                    return [i * dx for i in range(n_segments + 1)]

                while z <= math.pi/2:
                    if self.use_delta_height:
                        _3ctanz = _3c * math.tan(z)
                        ic00, ic01, ic10, ic11 = -1, -1, -1, -1
                        if a23cbxc + _3ctanz >= 0:
                            ic00 = (-a + math.sqrt(a23cbxc + _3ctanz))/_3c
                            ic01 = (-a - math.sqrt(a23cbxc + _3ctanz))/_3c
                        if a23cbxc - _3ctanz >= 0:
                            ic10 = (-a + math.sqrt(a23cbxc - _3ctanz))/_3c
                            ic11 = (-a - math.sqrt(a23cbxc - _3ctanz))/_3c

                        if 0 <= ic00 <= self.length:
                            samples.append(ic00)
                        if 0 <= ic01 <= self.length:
                            samples.append(ic01)
                        if 0 <= ic10 <= self.length:
                            samples.append(ic10)
                        if 0 <= ic11 <= self.length:
                            samples.append(ic11)
                    else:
                        # f_icurvature2(z, x) = (-b -x*c_d)/(2a) +- (tan z)/(2a)
                        t2a = math.tan(z)/(2*a)
                        ic20 = bxc2a + t2a
                        ic21 = bxc2a - t2a

                        if 0 <= ic20 <= self.length:
                            samples.append(ic20)
                        if 0 <= ic21 <= self.length:
                            samples.append(ic21)

                    z += spline_curve_sag * 10

            n_grad_samples = len(samples)

        # Now append the samples from the arc on the xz plane (spline radius)
        radius = abs(self.radius)
        dr = float("inf")
        if radius > 0:
            revs = min(self.length / radius, math.pi * 2)
            # Arc distance based angle increment
            dr_a = spline_tess_dist / radius
            # Sag distance based angle increment, clamped to 0.06deg < x < 90deg
            dr_b = 2 * math.acos(1 - clamp(spline_curve_sag / radius, 0.001, 0.294))
            dr = min(dr_a, dr_b)
            n_segments = max(math.ceil(revs / dr), 1)
            dr = revs / n_segments
            samples.extend([i*dr*radius for i in range(n_segments+1)])
        else:
            # Now append the samples from the constant tesselation factor
            # Note that the arc segment already include the constant tesselation factor
            n_segments = max(math.ceil(self.length / spline_tess_dist), 1)
            dx = self.length / n_segments
            samples.extend([i*dx for i in range(n_segments+1)])

        # Now weld the samples together based on a heuristic
        if len(samples) > 1:
            samples.sort()
            # This tuple stores the sample position, and it's weight (used for averaging); when a sample is consumed its
            # weight is set to 0 and the sample it's merged with has its weight incremented
            samples_weighted = [(s, 1) for s in samples]
            last_s = 0
            # log(f"spline-{self.id}\tmerge_dist: grad={(self.length/max(float(n_grad_samples), 0.1)/3):3f} "
            #     f"const={spline_tess_dist:3f} arc={dr*max(radius, 0.01)/2:3f} length={self.length*0.9:3f}")
            merge_dist = min((self.length/max(float(n_grad_samples), 0.1)/3),
                             spline_tess_dist,
                             dr*max(radius, 0.01)/2,
                             self.length*0.9)
            for i in range(1, len(samples_weighted)-1):
                d = samples_weighted[i][0] - samples_weighted[last_s][0]
                if d < merge_dist:
                    sl = samples_weighted[last_s]
                    samples_weighted[last_s] = ((sl[0]*sl[1]+samples_weighted[i][0]) / (sl[1]+1), sl[1]+1)
                    samples_weighted[i] = (0, 0)
                else:
                    last_s = i
            samples = [s[0] for s in samples_weighted if s[1] > 0]
            # Make sure the start and end points are fixed
            samples[0] = 0
            samples[-1] = self.length

        return samples

    def evaluate_spline(self, pos_offset, apply_rot=False, world_space=False):
        """
        Computes a position along a spline given offset coordinates.

        :param world_space: whether the position should be relative to the tile or relative to the origin of the
                            spline
        :param apply_rot: whether the spline segment's rotation should also be applied to the spline
        :param pos_offset: position offset along the spline; y is forward along the spline, x is across the
                           width of the spline
        :return: (the computed position, the computed rotation)
        """

        # Split the split evaluation into separate gradient and radius steps
        # Gradient
        # Evaluate: f_z(y, x) = y^3*c + y^2*a + y*b + x*(y*cant_delta + cant_0) {0 <= y <= length}
        # The rotation is given by:
        # f_rx(y, x) = atan(3y^2*c + 2y*a + b + x*cant_delta) {0 <= y <= length}
        ox, oy, oz = pos_offset
        cant_delta = (self.cant_end-self.cant_start)/100/self.length
        c, a, b = self._compute_spline_gradient_coeffs()
        pz = oy*oy*oy*c + oy*oy*a + oy*b
        rx = math.atan(3*oy*oy*c + 2*oy*a + b + ox*(oy*cant_delta + self.cant_start/100))

        pz += oz

        # Cant
        ry = math.atan(oy*cant_delta + self.cant_start/100)
        # TODO: The x coordinate should be clamped to the width of the spline
        pz += -ox*(oy*cant_delta + self.cant_start/100)

        # Radius
        if abs(self.radius) > 0:
            rz = oy/self.radius
            k = ox - self.radius
            px = k*math.cos(rz) + self.radius
            py = -k*math.sin(rz)
            rz = -rz
        else:
            rz = 0
            px = ox
            py = oy

        # World space
        pos = Vector((px, py, pz))
        rot = Vector((rx, ry, rz))
        if apply_rot or world_space:
            if bpy.app.version < (2, 80):
                pos = pos * mathutils.Matrix.Rotation(math.radians(self.rot), 4, "Z")
            else:
                pos = pos @ mathutils.Matrix.Rotation(math.radians(self.rot), 4, "Z")
            rot.z += math.radians(-self.rot)

        if world_space:
            pos += Vector(self.pos).xzy

        return pos, rot

    def generate_mesh(self, sli_cache, spline_tess_dist, spline_curve_sag, apply_xform = False):
        """
        Generates a Blender mesh for this spline.

        :param sli_cache: the dictionary of spline profile definitions
        :param spline_tess_dist: the distance between tesselation segments
        :param spline_curve_sag: the maximum amount of curve sag for the tessellated segments
        :param apply_xform:
        :return: a reference to the Blender mesh for this spline
        """
        sli = sli_cache[self.sli_path]
        verts = []
        uvs = []
        tris = []
        mat_ids = []
        v_count = 0

        if self.length == 0:
            return verts, tris, mat_ids, uvs

        segment_samples = self.generate_tesselation_points(spline_tess_dist, spline_curve_sag)

        for profile_part in sli[0]:
            profile_len = len(profile_part)
            m_verts = []
            for y in segment_samples:
                skew = (self.skew_start * (1 - y / self.length) + self.skew_end * y / self.length)
                if self.mirror:
                    skew = -skew
                line = [np.array([profile_part[p][0], skew * profile_part[p][0], profile_part[p][1]])
                        for p in range(profile_len)]

                if self.mirror:
                    for p in range(profile_len):
                        line[p][0] = -line[p][0]

                l_pos, l_rot = self.evaluate_spline([0, y, 0], apply_xform, apply_xform)

                # To prevent there from being a gap between profile segments, we don't rotate the segments in the x
                # direction
                l_rot.x = 0
                # Transform the profile lines by the evaluated position along the spline
                rot_matrix = mathutils.Euler(l_rot, 'XYZ')
                r_lines = [mathutils.Vector(line[p]) for p in range(profile_len)]
                [r_line.rotate(rot_matrix) for r_line in r_lines]
                line = [r_line + mathutils.Vector(l_pos) for r_line in r_lines]

                # Add to the vert list
                m_verts.extend(line)

                # Create UVs
                uvs.extend([(profile_part[p][2], (y+skew*profile_part[p][0]) * profile_part[p][3]) for p in range(profile_len)])

            # Construct triangles for the current strip (ie the current [profile])
            # The vertex array should look like this for a [profile] with three points:
            #   {End}
            # 9--10--11      6---7
            # | / | / |      | / |
            # 6---7---8      4---5
            # | / | / |      | / |
            # 3---4---5      2---3
            # | / | / |      | / |
            # 0---1---2      0---1
            #  {Start}       /\ For a profile with 2 points
            for x in range(len(segment_samples) - 1):
                for y in range(profile_len - 1):
                    if self.mirror:
                        # CW winding
                        tris.append((y + v_count + x * profile_len,  # 0 / 0
                                     y + v_count + (x + 1) * profile_len + 1,  # 4 / 3
                                     y + v_count + x * profile_len + 1))  # 1 / 1
                        tris.append((y + v_count + x * profile_len,  # 0 / 0
                                     y + v_count + (x + 1) * profile_len,  # 3 / 2
                                     y + v_count + (x + 1) * profile_len + 1))  # 4 / 3
                    else:
                        # CCW winding
                        tris.append((y + v_count + x * profile_len + 1,  # 1 / 1
                                     y + v_count + (x + 1) * profile_len + 1,  # 4 / 3
                                     y + v_count + x * profile_len))  # 0 / 0
                        tris.append((y + v_count + (x + 1) * profile_len + 1,  # 4 / 3
                                     y + v_count + (x + 1) * profile_len,  # 3 / 2
                                     y + v_count + x * profile_len))  # 0 / 0

            mat_ids.extend([profile_part[0][4] for x in range((len(segment_samples) - 1) * (profile_len - 1) * 2)])

            verts.extend(m_verts)
            v_count += len(m_verts)

        return verts, tris, mat_ids, uvs


def load_spline(sli_path, omsi_dir):
    """
    Loads a spline profile from a sli file.

    :param sli_path:
    :param omsi_dir:
    :return: (points: list(profile: list(point: list(x, z, uvx, y_tile, mat_id))), matls)
    """
    # Spline profiles are defined as a list of pairs of points. Each pair can have a different material and uvs.
    # We usually assume that the pairs join up with each other, but it is not required...
    if not os.path.isfile(os.path.join(omsi_dir, sli_path)):
        sli_path = os.path.join("Splines", "invis_street.sli")
        log("[WARNING] Spline profile {0} does not exist! Replacing with invis_street.sli instead...")
    with open(os.path.join(omsi_dir, sli_path), "r", encoding="utf-8", errors="replace") as f:
        curr_mat_idx = -1
        points = []
        matls = {}
        curr_matl = None
        lines = iter(f.readlines())
        for line in lines:
            if line.rstrip() == "[profile]":
                curr_mat_idx = int(next(lines))
                points.append([])
            elif line.rstrip() == "[profilepnt]":
                # x, z, uv_x, y_tilling, matID
                points[-1].append([float(next(lines)) for x in range(4)] + [curr_mat_idx])
            elif line.rstrip() == "[texture]":
                curr_matl = next(lines).rstrip().lower()
                matls[curr_matl] = {}
                matls[curr_matl]["diffuse"] = curr_matl
                tex_cfg = find_image_path(sli_path, curr_matl, False, True)
                if tex_cfg is not None:
                    tex_cfg = read_generic_cfg_file(tex_cfg)
                    if "[terrainmapping]" in tex_cfg:
                        matls[curr_matl]["diffuse"]["terrainmapping"] = True

            elif line.rstrip() == "[matl_alpha]":
                matls[curr_matl]["alpha"] = int(next(lines))
            elif line.rstrip() == "[patchwork_chain]":
                matls[curr_matl]["patchwork"] = (
                    int(next(lines)),
                    next(lines).rstrip(),
                    next(lines).rstrip(),
                    next(lines).rstrip(),
                )

    return points, matls


def load_spline_defs(map_file: dict):
    spline_defs = []
    splines = map_file.get("[spline]", []) + map_file.get("[spline_h]", [])
    splines.sort(key=lambda x: int(x[-2]))
    for local_id, lines in enumerate(splines):
        if lines[-1] == "[spline]":
            spline_defs.append(Spline(
                lines[1],  # path
                int(lines[2]),  # spline_id
                int(lines[3]),  # next_id
                int(lines[4]),  # prev_id
                [float(lines[5 + x]) for x in range(3)],  # pos
                float(lines[8]),  # rot
                float(lines[9]),  # length
                float(lines[10]),  # radius
                float(lines[11]),  # start_grad
                float(lines[12]),  # end_grad
                False,
                0,
                float(lines[13]),  # cant_start
                float(lines[14]),  # cant_end
                float(lines[15]),  # skew_start
                float(lines[16]),  # skew_end
                # lines[17], # length_accum, the accumulated length from all previous segments in this spline
                lines[18] == "mirror",  # mirror
                local_id  # local_id
            ))
        else:
            spline_defs.append(Spline(
                lines[1],  # path
                int(lines[2]),  # spline_id
                int(lines[3]),  # next_id
                int(lines[4]),  # prev_id
                [float(lines[5 + x]) for x in range(3)],  # pos
                float(lines[8]),  # rot
                float(lines[9]),  # length
                float(lines[10]),  # radius
                float(lines[11]),  # start_grad
                float(lines[12]),  # end_gra
                True,
                float(lines[13]),  # delta_height
                float(lines[14]),  # cant_start
                float(lines[15]),  # cant_en
                float(lines[16]),  # skew_start
                float(lines[17]),  # skew_end
                # lines[18], # length_accum, the accumulated length from all previous segments in this spline
                lines[19] == "mirror",  # mirror
                local_id  # local_id
            ))

    log("Loaded {0} splines!".format(len(spline_defs)))
    return spline_defs


def generate_materials(mesh, sli_path, matls):
    for matl in matls.values():
        mat_blender = bpy.data.materials.new(matl["diffuse"])
        if bpy.app.version < (2, 80):
            mat = mat_blender
            mat.diffuse_color = (1, 1, 1)
            mat.specular_hardness = 0.1
            mat.specular_intensity = 0
            mat.specular_color = (0.1, 0.1, 0.1)
        else:
            mat_blender.use_nodes = True
            mat = o3d_node_shader_utils.PrincipledBSDFWrapper(mat_blender, is_readonly=False)
            mat.base_color = (1, 1, 1)
            mat.specular = 0.1
            mat.roughness = 0.9

        # Load the diffuse texture and assign it to a new texture slot
        diff_tex = load_texture_into_new_slot(sli_path, matl["diffuse"], mat)
        if diff_tex:
            if bpy.app.version >= (2, 80):
                mat.base_color_texture.image = diff_tex.texture.image

            diff_tex.texture.image.colorspace_settings.name = 'sRGB'

            if "alpha" in matl and matl["alpha"] > 0:
                # Material uses alpha stored in diffuse texture alpha channel
                if bpy.app.version < (2, 80):
                    mat.use_transparency = True
                    diff_tex.use_map_alpha = True
                    diff_tex.alpha_factor = 1
                else:
                    mat.alpha_texture.image = diff_tex.texture.image

                mat.alpha = 0

        if bpy.app.version < (2, 80):
            pass
        else:
            mat_blender.use_backface_culling = True
            mat_blender.blend_method = "HASHED"
            mat_blender.shadow_method = "HASHED"

        mesh.materials.append(mat_blender)


def import_map_splines(filepath, map_file, spline_tess_dist, spline_curve_sag, parent_collection):
    """
    Imports all the splines in a given map tile and generates meshes for them.
    :param filepath:
    :param map_file:
    :param spline_tess_dist:
    :param spline_curve_sag:
    :param parent_collection:
    :return: (an array of Blender objects, a list of Spline definitions)
    """
    spline_defs = load_spline_defs(map_file)

    omsi_dir = os.path.abspath(os.path.join(os.path.dirname(filepath), os.pardir, os.pardir))
    spline_cache = {}
    for obj in spline_defs:
        if obj.sli_path not in spline_cache:
            spline_cache[obj.sli_path] = load_spline(obj.sli_path, omsi_dir)

    objs = []
    for spline in spline_defs:
        verts, tris, mat_ids, uvs = spline.generate_mesh(spline_cache, spline_tess_dist, spline_curve_sag)

        name = "spline-{0}".format(spline.id)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], tris)
        if bpy.app.version < (2, 80):
            mesh.uv_textures.new("UV Map")
        else:
            mesh.uv_layers.new(name="UV Map")

        values = [True] * len(mesh.polygons)
        mesh.polygons.foreach_set("use_smooth", values)

        mesh.update(calc_edges=True)

        for i, face in enumerate(mesh.polygons):
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                mesh.uv_layers[0].data[loop_idx].uv = uvs[vert_idx]

            face.material_index = mat_ids[i]

        # Generate materials for the spline
        generate_materials(mesh, os.path.join(omsi_dir, spline.sli_path), spline_cache[spline.sli_path][1])

        # Create a blender object from the mesh and set its transform
        create_spline_obj(mesh, name, objs, parent_collection, spline)

    return objs, spline_defs


def import_map_preview_splines(filepath, map_file, spline_tess_dist, parent_collection, mesh_gen=False):
    """
    Imports all the splines in a given map tile and generates preview curves for them.
    :param filepath:
    :param map_file:
    :param spline_tess_dist:
    :param parent_collection:
    :param mesh_gen:
    :return: (an array of Blender objects, a list of Spline definitions)
    """
    spline_defs = load_spline_defs(map_file)

    omsi_dir = os.path.abspath(os.path.join(os.path.dirname(filepath), os.pardir, os.pardir))
    for spline in spline_defs:
        spline.use_delta_height = False
        spline.end_grad = 0
        spline.start_grad = 0
        spline.cant_start = 0
        spline.cant_end = 0
        spline.delta_height = 0
        spline.pos[1] = 0

    spline_cache = {}
    if mesh_gen:
        for obj in spline_defs:
            if obj.sli_path not in spline_cache:
                sli_points, matls = load_spline(obj.sli_path, omsi_dir)
                matls = list(matls.values())

                # Simplify the spline, determine the total width of the spline and just use that as
                min_x = 0
                max_x = 0
                for profile in sli_points:
                    if len(profile) > 0:
                        mat_id = profile[0][4]
                        if mat_id >= len(matls) or "terrainmapping" in matls[mat_id]:
                            continue

                    for point in profile:
                        min_x = min(min_x, point[0])
                        max_x = max(max_x, point[0])
                sli_points = [[[min_x, 0.25, 0, 1, 0], [max_x, 0.25, 1, 1, 0]]]

                spline_cache[obj.sli_path] = (sli_points, matls)

    objs = []
    if mesh_gen:
        spline_bdata = bpy.data.meshes.new("merged-splines")
    else:
        spline_bdata = bpy.data.curves.new("merged-splines", type='CURVE')
        spline_bdata.dimensions = '3D'
        spline_bdata.resolution_u = 2

    # Create a blender object from the mesh and set its transform
    o = bpy.data.objects.new("merged-splines", spline_bdata)
    objs.append(o)

    if bpy.app.version < (2, 80):
        bpy.context.scene.objects.link(o)
        parent_collection.objects.link(o)

        o.select = True
    else:
        parent_collection.objects.link(o)
        o.select_set(True)

    verts = []
    tris = []
    for spline in spline_defs:
        if mesh_gen:
            verts_inst, tris_inst, mat_ids, uvs = spline.generate_mesh(spline_cache, spline_tess_dist, 1000,
                                                                       apply_xform=True)
            tris_inst = np.add(tris_inst, len(verts))
            verts.extend(verts_inst)
            tris.extend(tris_inst)
        else:
            # map coords to spline
            polyline = spline_bdata.splines.new('POLY')
            if spline.length > 0:
                n_points = max(math.floor(spline.length/spline_tess_dist), 2)
                polyline.points.add(n_points-1)
                for i in range(n_points):
                    x, y, z = spline.evaluate_spline((0, i/(n_points-1)*spline.length, 0), True, True)[0]
                    polyline.points[i].co = (x, y, z, 1)

    if mesh_gen:
        spline_bdata.from_pydata(verts, [], tris)

        values = [True] * len(spline_bdata.polygons)
        spline_bdata.polygons.foreach_set("use_smooth", values)

        spline_bdata.update(calc_edges=True)

        spline_bdata.materials.append(o3d_node_shader_utils.generate_solid_material((0.8, 0.8, 0.8, 1.)))

    return objs, spline_defs


def create_spline_obj(mesh, name, objs, parent_collection, spline):
    o = bpy.data.objects.new(name, mesh)
    objs.append(o)
    # Cache spline creation params
    bpy.data.objects[o.name]["spline_def"] = spline.__dict__
    o.location = [spline.pos[0], spline.pos[2], spline.pos[1]]
    o.rotation_euler = [0, 0, math.radians(-spline.rot)]
    if bpy.app.version < (2, 80):
        bpy.context.scene.objects.link(o)
        parent_collection.objects.link(o)

        o.select = True
    else:
        parent_collection.objects.link(o)
        o.select_set(True)
