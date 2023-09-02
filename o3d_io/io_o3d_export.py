# ==============================================================================
#  Copyright (c) 2022-2023 Thomas Mathieson.
# ==============================================================================

import os
import time

import numpy as np

import bmesh
import bpy
from mathutils import Matrix
from . import o3d_cfg_parser, o3dconvert

if not (bpy.app.version[0] < 3 and bpy.app.version[1] < 80):
    from bpy_extras import node_shader_utils


def log(*args):
    print("[O3D_Export]", *args)


def export_mesh(filepath, context, blender_obj, mesh, transform_matrix, materials, o3d_version, export_custom_normals):
    # Create o3d file
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        has_uvs = len(mesh.uv_layers) > 0
        if has_uvs:
            uv_layer = mesh.uv_layers.active.data[:]
        else:
            uv_layer = None

        # Extract mesh data
        tris = []
        verts = []  # Array of (xp, yp, zp, xn, yn, zn, u, v)
        vert_map = {}
        vert_count = 0

        if bpy.app.version < (2, 80):
            mesh.calc_normals_split()
            mesh.calc_tessface()
            uv_layer = mesh.tessface_uv_textures.active
            for face in mesh.tessfaces:
                face_inds = []

                face_len = len(face.vertices)
                for i in range(face_len):
                    v_co = mesh.vertices[face.vertices[i]].co[:]
                    v_nrm = face.split_normals[i][:]
                    if uv_layer is not None:
                        v_uv = uv_layer.data[face.index].uv[i][:]
                    else:
                        v_uv = (0, 0)

                    if (v_co, v_nrm, v_uv) in vert_map:
                        face_inds.append(vert_map[(v_co, v_nrm, v_uv)])
                    else:
                        vert_map[(v_co, v_nrm, v_uv)] = vert_count
                        verts.append(
                            [v_co[0], v_co[1], v_co[2],
                             v_nrm[0], v_nrm[1], v_nrm[2],
                             v_uv[0], 1 - v_uv[1]])

                        face_inds.append(vert_count)

                        vert_count += 1

                # Create the triangle
                if face_len >= 3:
                    tris.append((face_inds[0], face_inds[1], face_inds[2], face.material_index))

                # Sometimes we have to deal with quads...
                # 2---3
                # | \ |
                # 0---1
                if face_len >= 4:
                    tris.append((face_inds[1], face_inds[3], face_inds[2], face.material_index))
        else:
            mesh.calc_loop_triangles()
            if export_custom_normals and mesh.has_custom_normals:
                # mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
                mesh.use_auto_smooth = True
            else:
                mesh.free_normals_split()
            mesh.calc_normals_split()
            for tri_loop in mesh.loop_triangles:
                tri = []
                tris.append(tri)

                for tri_vert, loop, normal in zip(tri_loop.vertices, tri_loop.loops, tri_loop.split_normals):
                    vert = mesh.vertices[tri_vert]
                    v_co = vert.co[:]
                    v_nrm = mesh.loops[loop].normal[:]
                    if uv_layer is not None:
                        v_uv = uv_layer[loop].uv[:2]
                    else:
                        v_uv = (0, 0)

                    if (v_co, v_nrm, v_uv) in vert_map:
                        tri.append(vert_map[(v_co, v_nrm, v_uv)])
                    else:
                        vert_map[(v_co, v_nrm, v_uv)] = vert_count
                        verts.append(
                            [v_co[0], v_co[1], v_co[2],
                             -v_nrm[0], -v_nrm[1], -v_nrm[2],
                             v_uv[0], 1 - v_uv[1]])
                        tri.append(vert_count)
                        vert_count += 1

                tri.append(tri_loop.material_index)

        # Construct embedded material array
        o3d_mats = []
        for mat in materials:
            # O3D mat structure:
            # (diffuse_r, diffuse_g, diffuse_b, diffuse_a, specular_r, specular_g, specular_b, emission_r, emission_g,
            #  emission_b, specular_power, texture_name)
            o3d_mat = []
            o3d_mats.append(o3d_mat)
            if bpy.app.version < (2, 80):
                mat = mat.material
                o3d_mat.extend(mat.diffuse_color)
                o3d_mat.append(mat.alpha)
                o3d_mat.extend(np.array(mat.specular_color) * mat.specular_intensity)
                o3d_mat.extend(np.array(mat.diffuse_color) * mat.emit)
                o3d_mat.append(mat.specular_hardness)
                texture_data = ""
                for i, texture in reversed(list(enumerate(mat.texture_slots))):
                    if texture is None or texture.texture_coords != 'UV' or not texture.use_map_color_diffuse:
                        continue
                    texture_data = bpy.data.textures[texture.name]
                    if texture_data.type != 'IMAGE' or texture_data.image is None or not mat.use_textures[i]:
                        continue
                    texture_data = texture_data.image.name

                o3d_mat.append(texture_data)
            else:
                mat = node_shader_utils.PrincipledBSDFWrapper(mat.material, is_readonly=True)
                o3d_mat.extend(mat.base_color[:3])
                o3d_mat.append(mat.alpha)
                o3d_mat.extend([mat.specular, mat.specular, mat.specular])
                o3d_mat.extend(mat.emission_color[:3])
                o3d_mat.append(1 - mat.roughness)
                if mat.base_color_texture is not None and mat.base_color_texture.image is not None:
                    o3d_mat.append(os.path.basename(mat.base_color_texture.image.filepath))
                else:
                    o3d_mat.append("")

        # Construct bones
        bones = []
        for v_group in blender_obj.vertex_groups:
            bone = (v_group.name, [])
            bones.append(bone)
            for index in range(len(verts)):
                try:
                    bone[1].append((index, v_group.weight(index)))
                except Exception as e:
                    pass

        o3dconvert.export_o3d(f, verts, tris, o3d_mats, bones, transform_matrix,
                              version=o3d_version,
                              encrypted=False, encryption_key=0x0,
                              long_triangle_indices=False,
                              alt_encryption_seed=True,
                              invert_triangle_winding=True)


def do_export(filepath, context, global_matrix, use_selection, o3d_version, export_custom_normals=True):
    """
    Exports the selected CFG/SCO/O3D file
    :param o3d_version: O3D version to export the file as
    :param use_selection: export only the selected objects
    :param global_matrix: transformation matrix to apply before export
    :param filepath: the path to the file to import
    :param context: blender context
    :return: success message
    """
    obj_root = os.path.dirname(filepath)
    start_time = time.time()

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')

    if use_selection:
        obs = context.selected_objects
    else:
        obs = context.scene.objects

    if bpy.app.version < (2, 80):
        deps_graph = None
    else:
        deps_graph = context.evaluated_depsgraph_get()

    bpy.context.window_manager.progress_begin(0, len(obs))

    single_o3d = False
    if filepath[-3:] == "o3d":
        single_o3d = True

    index = 0
    exported_paths = set()
    for ob in obs:
        if "skip_export" in ob:
            log("Skipping {0}...".format(ob.name))
            index += 1
            continue

        log("Exporting " + ob.name + "...")
        bpy.context.window_manager.progress_update(index)
        if bpy.app.version < (2, 80):
            ob_eval = ob

            try:
                me = ob_eval.to_mesh(context.scene, True, 'PREVIEW')
            except RuntimeError:
                continue
        else:
            ob_eval = ob.evaluated_get(deps_graph)

            try:
                me = ob_eval.to_mesh()
            except RuntimeError:
                continue

        axis_conversion_matrix = Matrix((
            (1, 0, 0, 0),
            (0, 0, 1, 0),
            (0, 1, 0, 0),
            (0, 0, 0, 1)
        ))

        if bpy.app.version < (2, 80):
            o3d_matrix = axis_conversion_matrix * ob.matrix_world * axis_conversion_matrix
        else:
            o3d_matrix = axis_conversion_matrix @ ob.matrix_world @ axis_conversion_matrix
        o3d_matrix.transpose()
        me.transform(ob.matrix_world)
        me.transform(axis_conversion_matrix)
        if ob.matrix_world.is_negative:
            me.flip_normals()

        log("Exported matrix: \n{0}".format(o3d_matrix))

        bm = bmesh.new()
        bm.from_mesh(me)

        if global_matrix is not None:
            bm.transform(global_matrix)

        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method=0, ngon_method=0)
        else:
            bmesh.ops.triangulate(bm, faces=bm.faces)

        bm.to_mesh(me)
        bm.free()

        me.calc_normals_split()

        # Export individual model
        if "export_path" in ob:
            path = os.path.join(obj_root, ob["export_path"])
        else:
            path = os.path.join(obj_root, ob.name + ".o3d")

        if single_o3d:
            if len(obs) == 1:
                path = filepath
            else:
                path = os.path.join(obj_root, os.path.basename(filepath)[:-4] + "-" + ob.name + ".o3d")

        # Export the mesh if it hasn't already been exported
        if path not in exported_paths:
            exported_paths.add(path)
            export_mesh(path, context, ob_eval, me, [x for y in o3d_matrix for x in y], ob_eval.material_slots,
                        o3d_version, export_custom_normals)

        index += 1

    if not single_o3d:
        cfg_materials = o3d_cfg_parser.write_cfg(filepath, obs, context, use_selection)

    bpy.context.window_manager.progress_end()
    log("Exported {0} models in {1} seconds!".format(len(obs), time.time() - start_time))
