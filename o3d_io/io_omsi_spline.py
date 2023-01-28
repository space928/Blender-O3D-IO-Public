# ==============================================================================
#  Copyright (c) 2022 Thomas Mathieson.
# ==============================================================================
import os

import bpy
from . import o3d_node_shader_utils
from .blender_texture_io import load_texture_into_new_slot
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
                 start_grad, end_grad, cant_start, cant_end, skew_start, skew_end,
                 mirror):
        self.sli_path = sli_path
        self.id = spline_id
        self.nextID = next_id
        self.prevID = prev_id
        self.pos = pos
        self.rot = rot
        self.length = length
        self.radius = radius
        self.startGrad = start_grad
        self.endGrad = end_grad
        self.cantStart = cant_start
        self.cantEnd = cant_end
        self.skewStart = skew_start
        self.skewEnd = skew_end
        self.mirror = mirror

    def __str__(self) -> str:
        return f"Spline {self.id}: sli_path = {self.sli_path}; id = {self.id}; nextID = {self.nextID}; " \
               f"prevID = {self.prevID}; pos = {self.pos}; rot = {self.rot}; length = {self.length}; " \
               f"radius = {self.radius}; startGrad = {self.startGrad}; endGrad = {self.endGrad}; " \
               f"cantStart = {self.cantStart}; cantEnd = {self.cantEnd}; skewStart = {self.skewStart}; " \
               f"skewEnd = {self.skewEnd}; mirror = {self.mirror}. "

    def generate_mesh(self, sli_cache, spline_tess_dist, spline_curve_sag):
        sli = sli_cache[self.sli_path]
        verts = []
        uvs = []
        tris = []
        mat_ids = []
        v_count = 0

        if self.length == 0:
            return verts, tris, mat_ids, uvs

        # Work out what tessellation increment we should use, this will always be greater than or equal to the one
        # specified but needs to be the correct size to divide the length into a whole number of segments
        dx = min(self.length / math.ceil(self.length / spline_tess_dist), self.length)
        # How much to rotate at each step in radians such that the average arc distance ~= spline_tess_dist
        rot_dir = math.copysign(1, self.radius)
        self.radius = abs(self.radius)
        if self.radius > 0:
            revs = min(self.length / self.radius, math.pi * 2)
            # Arc distance based angle increment
            dr_a = spline_tess_dist / self.radius
            # Sag distance based angle increment, clamped to 0.06deg < x < 90deg
            dr_b = 2 * math.acos(1 - clamp(spline_curve_sag / self.radius, 0.001, 0.294))
            dr = min(dr_a, dr_b)
            dr = min(revs / math.ceil(revs / dr), revs)
            # log(f"len={self.length:.3f} rad={self.radius:.3f} revs={revs*180/math.pi:.3f} "
            #     f"dr_a={dr_a*180/math.pi:.3f} dr_b={dr_b:.3f} dbg={1 - spline_curve_sag / self.radius}"
            #     f"dr={dr*180/math.pi:.3f}")
        else:
            dr = 0

        for profile_part in sli[0]:
            pos_offset = mathutils.Vector((0, dx if self.radius <= 0 else 0, 0))
            curr_len = 0
            curr_pos = np.array((0.0, 0.0, 0.0))
            curr_rot = [0.09 * self.startGrad, -0.09 * self.cantStart, 0]
            curve_rot_ang = 0
            m_verts = []
            while abs(curr_len) <= self.length:
                skew = (self.skewStart * (1 - curr_len / self.length) + self.skewEnd * curr_len / self.length)
                line = [np.array([profile_part[0][0], skew * profile_part[0][0], profile_part[0][1]]),
                        np.array([profile_part[1][0], skew * profile_part[1][0], profile_part[1][1]])]
                # Transform the slice
                # rot_matrix = R.from_euler("xyz", curr_rot, degrees=True)
                rot_matrix = mathutils.Euler((math.radians(curr_rot[0]), math.radians(curr_rot[1]),
                                              0), 'XYZ')

                if self.mirror:
                    line[0][0] = -line[0][0]
                    line[1][0] = -line[1][0]

                r_line0 = mathutils.Vector(line[0])
                r_line1 = mathutils.Vector(line[1])
                r_line0.rotate(rot_matrix)
                r_line1.rotate(rot_matrix)

                if self.radius > 0:
                    curve_rot = mathutils.Matrix.Translation((self.radius * rot_dir, 0, 0)) \
                                @ mathutils.Matrix.Rotation(curve_rot_ang, 4, "Z") \
                                @ mathutils.Matrix.Translation((-self.radius * rot_dir, 0, 0))
                    r_line0 = curve_rot @ r_line0
                    r_line1 = curve_rot @ r_line1

                line[0] = np.array(r_line0) + curr_pos
                line[1] = np.array(r_line1) + curr_pos

                # line[0][1] = -line[0][1]
                # line[1][1] = -line[1][1]
                # line[0][0] = -line[0][0]
                # line[1][0] = -line[1][0]

                # Add to the vert list
                m_verts.extend(line)

                # Create UVs
                uvs.append([profile_part[0][2], curr_len * profile_part[0][3]])
                uvs.append([profile_part[1][2], curr_len * profile_part[1][3]])

                # Increment position and rotation
                pos_offset.rotate(rot_matrix)
                curr_pos += np.array(pos_offset)
                curve_rot_ang -= dr * rot_dir
                # if self.radius > 0:
                #     curr_rot[2] += 180 / math.pi * dx / self.radius

                curr_rot[0] = 0.09 * (
                        self.startGrad * (1 - curr_len / self.length) + self.endGrad * curr_len / self.length)
                curr_rot[1] = -0.09 * (
                        self.cantStart * (1 - curr_len / self.length) + self.cantEnd * curr_len / self.length)

                if self.radius > 0:
                    curr_len += dr * self.radius * rot_dir
                else:
                    curr_len += dx

            for x in range(len(m_verts) // 2 - 1):
                if self.mirror:
                    tris.append((v_count + x * 2, v_count + x * 2 + 3, v_count + x * 2 + 1))
                    tris.append((v_count + x * 2, v_count + x * 2 + 2, v_count + x * 2 + 3))
                else:
                    tris.append((v_count + x * 2 + 1, v_count + x * 2 + 3, v_count + x * 2))
                    tris.append((v_count + x * 2 + 3, v_count + x * 2 + 2, v_count + x * 2))

            mat_ids.extend([profile_part[0][4] for x in range(len(m_verts) - 2)])

            verts.extend(m_verts)
            v_count += len(m_verts)

        self.radius *= rot_dir
        return verts, tris, mat_ids, uvs


def load_spline(sli_path, omsi_dir):
    # Spline profiles are defined as a list of pairs of points. Each pair can have a different material and uvs.
    # We usually assume that the pairs join up with each other, but it is not required...
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


def load_spline_defs(map_file):
    spline_defs = []
    for lines in map_file.get("[spline]", []) + map_file.get("[spline_h]", []):
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
            float(lines[13]),  # cant_start
            float(lines[14]),  # cant_en
            float(lines[15]),  # skew_start
            float(lines[16]),  # skew_end
            lines[18] == "mirror"  # mirror
        ))
    log(f"Loaded {len(spline_defs)} splines!")
    return spline_defs


def generate_materials(mesh, sli_path, matls):
    for matl in matls.values():
        mat_blender = bpy.data.materials.new(matl["diffuse"])
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
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
            if not (bpy.app.version[0] < 3 and bpy.app.version[1] < 80):
                mat.base_color_texture.image = diff_tex.texture.image

            diff_tex.texture.image.colorspace_settings.name = 'sRGB'

            if "alpha" in matl and matl["alpha"] > 0:
                # Material uses alpha stored in diffuse texture alpha channel
                if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                    mat.use_transparency = True
                    diff_tex.use_map_alpha = True
                    diff_tex.alpha_factor = 1
                else:
                    mat.alpha_texture.image = diff_tex.texture.image

                mat.alpha = 0

        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            pass
        else:
            mat_blender.use_backface_culling = True
            mat_blender.blend_method = "HASHED"
            mat_blender.shadow_method = "HASHED"

        mesh.materials.append(mat_blender)


def import_map_splines(filepath, map_file, spline_tess_dist, spline_curve_sag):
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
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            mesh.uv_textures.new("UV Map")
        else:
            mesh.uv_layers.new(name="UV Map")

        mesh.update(calc_edges=True)

        for i, face in enumerate(mesh.polygons):
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                mesh.uv_layers[0].data[loop_idx].uv = uvs[vert_idx]

            face.material_index = mat_ids[i]

        # Generate materials for the spline
        generate_materials(mesh, os.path.join(omsi_dir, spline.sli_path), spline_cache[spline.sli_path][1])

        # Create a blender object from the mesh and set its transform
        o = bpy.data.objects.new(name, mesh)
        objs.append(o)

        # Cache spline creation params
        bpy.data.objects[o.name]["spline_def"] = spline.__dict__

        o.location = [spline.pos[0], spline.pos[2], spline.pos[1]]
        o.rotation_euler = [0, 0, math.radians(-spline.rot)]

        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            scene = bpy.context.scene
            scene.objects.link(o)

            o.select = True
        else:
            view_layer = bpy.context.view_layer
            collection = view_layer.active_layer_collection.collection

            collection.objects.link(o)
            o.select_set(True)

    return objs
