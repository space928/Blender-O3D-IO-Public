# ==============================================================================
#  Copyright (c) 2022-2023 Thomas Mathieson.
# ==============================================================================
import math
import time
from math import radians

import numpy as np

import bpy
import os

if bpy.app.version >= (2, 80):
    # from bpy_extras import node_shader_utils
    from . import o3d_node_shader_utils
from . import o3dconvert

# from . import log
from mathutils import Matrix, Vector
from .o3d_cfg_parser import read_cfg
from .blender_texture_io import load_texture_into_new_slot, load_image


def log(*args):
    print("[O3D_Import]", *args)


def platform_related_path(path):
    """
    Return a string with correct path separators for the current platform
    :param path: the path to convert
    :return: the converted path
    """
    return path.replace("/", os.sep).replace("\\", os.sep)


def do_import(filepath, context, import_x, override_text_encoding, hide_lods, import_lods=True, parent_collection=None,
              split_normals=True):
    """
    Imports the selected CFG/SCO/O3D file
    :param override_text_encoding: the text encoding to use to read the file instead of utf8/cp1252
    :param import_x: whether to attempt to import referenced .x files
    :param hide_lods: whether additional LODs should be hidden by default
    :param filepath: the path to the file to import
    :param context: blender context
    :param import_lods: whether additional LODs should be loaded
    :param parent_collection: which current_collection to parent the imported objects to, use None for the scene current_collection
    :return: success message
    """
    obj_root = os.path.dirname(filepath)
    start_time = time.time()
    if filepath[-3:] == "o3d" or filepath[-3:] == "rdy":
        cfg_data = {
            -1: {
                "meshes": {
                    filepath: {
                        "path": filepath,
                    }
                }
            }
        }
    else:
        (cfg_data, obj_root) = read_cfg(filepath, override_text_encoding)

    n_meshes = len([0 for lod in cfg_data for mesh in cfg_data[lod]["meshes"]])
    bpy.context.window_manager.progress_begin(0, n_meshes)

    sorted_lods = sorted(cfg_data.keys(), reverse=True)

    # Work out where to put any custom data belonging to the root of the CFG file
    # In this case we CAN'T use the scene collection since it doesn't expose custom data in the editor for some reason
    custom_data_object = parent_collection
    if custom_data_object is None \
            or (bpy.app.version >= (2, 80) and custom_data_object == context.scene.collection):
        custom_data_object = bpy.data.scenes[context.scene.name]

    # Iterate through the selected files
    blender_objs = []
    mat_counter = 0
    mesh_index = 0
    is_highest_lod = True
    current_collection = None
    for current_lod in sorted_lods:
        if not import_lods and not is_highest_lod:
            continue

        if bpy.app.version < (2, 80):
            if current_lod == -1 or not import_lods:
                current_collection = parent_collection
            else:
                collection_name = "LOD_{0}".format(current_lod)
                if collection_name not in bpy.data.groups:
                    current_collection = bpy.data.groups.new(collection_name)
                    if parent_collection is not None:
                        parent_collection.objects.link(current_collection)
                else:
                    current_collection = bpy.data.groups[collection_name]
        else:
            if current_lod == -1 or not import_lods:
                current_collection = bpy.context.scene.collection
                if parent_collection is not None:
                    current_collection = parent_collection
            else:
                collection_name = "LOD_{0}".format(current_lod)
                if collection_name not in bpy.data.collections:
                    current_collection = bpy.data.collections.new(collection_name)
                    if parent_collection is not None:
                        parent_collection.children.link(current_collection)
                    else:
                        bpy.context.scene.collection.children.link(current_collection)
                else:
                    current_collection = bpy.data.collections[collection_name]

        for current_mesh in cfg_data[current_lod]["meshes"]:
            # Generate full path to file
            path_to_file = cfg_data[current_lod]["meshes"][current_mesh]["path"]
            path_to_file = platform_related_path(path_to_file)
            bpy.context.window_manager.progress_update(mesh_index)
            log("[{0:.2f}%] Loading {1}...".format((mesh_index + 1) / n_meshes * 100, path_to_file))

            if path_to_file[-1:] == "x":
                if not import_x:
                    bpy.ops.object.select_all(action='DESELECT')
                    continue

                # X files are not supported by this importer
                try:
                    x_file_path = {"name": os.path.basename(path_to_file)}
                    # Clunky solution to work out what has been imported because the x importer doesn't set selection
                    old_objs = set(context.scene.objects)
                    # For now the x file importer doesn't handle omsi x files very well, materials aren't imported
                    # correctly
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.ops.import_scene.x(filepath=path_to_file, files=[x_file_path], axis_forward='Y', axis_up='Z',
                                           use_split_objects=False, use_split_groups=False, parented=False,
                                           quickmode=True)
                    # mat_counter = generate_materials(cfg_materials, filepath, mat_counter, materials, mesh,
                    #                                  object_directory, path_to_file)
                    new_objs = set(context.scene.objects) - old_objs

                    for o in new_objs:
                        if current_collection is not None:
                            if bpy.app.version > (2, 79):
                                if current_collection != bpy.context.scene.collection:
                                    bpy.context.scene.collection.objects.unlink(o)
                                if current_collection in o.users_collection:
                                    continue
                            # else:
                            #     bpy.context.scene.objects.unlink(o)
                            current_collection.objects.link(o)

                    # Create lights
                    create_lights(blender_objs, cfg_data[current_lod]["meshes"][current_mesh], filepath,
                                  current_collection)
                    blender_objs.extend(new_objs)
                    continue
                except Exception as e:
                    log("WARNING: {0} was not imported! A compatible X importer was not found! Please use: "
                        "https://github.com/Poikilos/io_import_x\n"
                        "Exception: {1}".format(path_to_file, e))
                    continue

            # Load mesh
            materials, matl_ids, mesh, o3d, o3d_transform_matrix = load_o3d(obj_root, path_to_file, split_normals)
            if mesh is None:
                continue

            # Create blender object
            blender_obj = None
            if bpy.app.version < (2, 80):
                blender_obj = bpy.data.objects.new(path_to_file[len(obj_root):-4], mesh)
                blender_obj["export_path"] = path_to_file[len(obj_root):]
                blender_objs.append(blender_obj)
                scene = bpy.context.scene
                scene.objects.link(blender_obj)

                # In this case current_collection is actually a group and not a collection, but they're functionally
                # the same
                if current_collection is not None:
                    current_collection.objects.link(blender_obj)

                if hide_lods and not is_highest_lod:
                    # Check this works in 2.79...
                    blender_obj.hide = True
                    blender_obj.hide_render = True
            else:
                blender_obj = bpy.data.objects.new(path_to_file[len(obj_root):-4], mesh)
                blender_obj["export_path"] = path_to_file[len(obj_root):]
                blender_objs.append(blender_obj)

                current_collection.objects.link(blender_obj)

                if hide_lods and not is_highest_lod:
                    blender_obj.hide_set(True)
                    blender_obj.hide_render = True

            # Transform object
            blender_obj.matrix_basis = o3d_transform_matrix

            # Generate materials
            cfg_mats = cfg_data[current_lod]["meshes"][current_mesh].get("matls", {})
            mat_counter = generate_materials(cfg_mats, filepath,
                                             mat_counter, materials, mesh)

            # Populate remaining properties on the mesh
            bpy.data.meshes[mesh.name]["cfg_data"] = cfg_data[current_lod]["meshes"][current_mesh].get("cfg_data", {})
            # for prop in cfg_data[current_file[2]]["meshes"][current_file[1]].items():
            #     if prop[0][0] == "[" and prop[0][-1] == "]":
            #         # This must be an unparsed property, therefore we add it to the custom properties of the mesh
            #         bpy.data.meshes[mesh.name][prop[0]] = prop[1]

            for ind, tri in enumerate(mesh.polygons):
                tri.material_index = matl_ids[ind]

            mesh.update()

            # Generate bones
            for bone in o3d[4]:
                blender_obj.vertex_groups.new(name=bone[0])
                for vert in bone[1]:
                    blender_obj.vertex_groups[bone[0]].add([vert[0]], vert[1], "REPLACE")

            mesh_index += 1

        # Remove the is_highest_lod flag once we've imported the highest LOD, note that LOD -1 should always import
        # first, but isn't the highest LOD (unless no other LODs are loaded)
        if current_lod != -1:
            is_highest_lod = False

        # Create lights
        create_lights(blender_objs, cfg_data[current_lod], filepath, current_collection)

    # Populate remaining properties on the cfg
    if "cfg_data" in cfg_data[-1]:
        custom_data_object["cfg_data"] = cfg_data[-1]["cfg_data"]
    if "groups" in cfg_data[-1]:
        custom_data_object["groups"] = cfg_data[-1]["groups"]
    if "friendlyname" in cfg_data[-1]:
        custom_data_object["friendlyname"] = cfg_data[-1]["friendlyname"]
    if "editor_only" in cfg_data[-1]:
        custom_data_object["editor_only"] = cfg_data[-1]["editor_only"]
    if "tree" in cfg_data[-1]:
        custom_data_object["tree"] = cfg_data[-1]["tree"]

    bpy.ops.object.select_all(action='DESELECT')
    try:
        for x in blender_objs:
            if bpy.app.version < (2, 80):
                x.select = True
            else:
                x.select_set(True)
    except Exception as e:
        log("WARNING: Couldn't select loaded objects:", e)

    if n_meshes == 0:
        log("WARNING: 0 models loaded! File:", filepath)

    log("Loaded {0} models in {1} seconds!".format(n_meshes, time.time() - start_time))
    return blender_objs


def create_lights(blender_objs, cfg_data, filepath, collection):
    interior_lights = cfg_data.get("interior_lights", [])
    for light_ind, light_cfg in enumerate(interior_lights):
        light_name = "::interior_light_{0}".format(light_ind)

        if bpy.app.version < (2, 80):
            light_data = bpy.data.lamps.new(name=light_name, type='POINT')
            light_data.distance = light_cfg["range"]
            light_data.energy = 0.04
            light_data.color = (light_cfg["red"], light_cfg["green"], light_cfg["blue"])
            light_data["variable"] = light_cfg["variable"]
            light_data["cfg_type"] = "interiorlight"

            light_object = bpy.data.objects.new(name=light_name, object_data=light_data)

            bpy.context.scene.objects.link(light_object)
            if collection is not None:
                collection.objects.link(light_object)

        else:
            light_data = bpy.data.lights.new(name=light_name, type='POINT')
            light_data.energy = light_cfg["range"] * 10.0
            light_data.color = (light_cfg["red"], light_cfg["green"], light_cfg["blue"])
            light_data.shadow_soft_size = 0.02
            light_data["variable"] = light_cfg["variable"]
            light_data["cfg_type"] = "interiorlight"

            light_object = bpy.data.objects.new(name=light_name, object_data=light_data)

            collection.objects.link(light_object)

        blender_objs.append(light_object)
        # light_object.parent = blender_obj
        # Change light position
        light_object.location = (light_cfg["x_pos"], light_cfg["y_pos"], light_cfg["z_pos"])

    spotlights = cfg_data.get("spotlights", {})
    for light_ind, light_cfg in enumerate(spotlights):
        light_name = "::spotlight_{0}".format(light_ind)

        if bpy.app.version < (2, 80):
            light_data = bpy.data.lamps.new(name=light_name, type='SPOT')
            light_data.distance = light_cfg["range"]
            light_data.energy = 0.04
            light_data.color = (light_cfg["col_r"], light_cfg["col_g"], light_cfg["col_b"])

            light_data.spot_size = math.radians(light_cfg["outer_angle"])
            light_data.spot_blend = light_cfg["inner_angle"] / light_cfg["outer_angle"]
            light_data["cfg_type"] = "spotlight"

            light_object = bpy.data.objects.new(name=light_name, object_data=light_data)

            bpy.context.scene.objects.link(light_object)
            if collection is not None:
                collection.objects.link(light_object)
        else:
            light_data = bpy.data.lights.new(name=light_name, type='SPOT')
            light_data.energy = light_cfg["range"] * 10.0
            light_data.color = (light_cfg["col_r"], light_cfg["col_g"], light_cfg["col_b"])
            light_data.shadow_soft_size = 0.02
            light_data.spot_size = math.radians(light_cfg["outer_angle"])
            light_data.spot_blend = light_cfg["inner_angle"] / light_cfg["outer_angle"]
            light_data["cfg_type"] = "spotlight"

            light_object = bpy.data.objects.new(name=light_name, object_data=light_data)

            collection.objects.link(light_object)

        blender_objs.append(light_object)
        # light_object.parent = blender_obj

        # Change light position
        light_object.location = (light_cfg["x_pos"], light_cfg["y_pos"], light_cfg["z_pos"])

        v0 = Vector((0, 0, 1))
        v1 = Vector((light_cfg["x_fwd"], light_cfg["y_fwd"], -light_cfg["z_fwd"]))

        light_object.rotation_euler = v1.rotation_difference(v0).to_euler()

    maplights = cfg_data.get("maplights", [])
    for light_ind, light_cfg in enumerate(maplights):
        light_name = "::maplight_{0}".format(light_ind)

        if bpy.app.version < (2, 80):
            light_data = bpy.data.lamps.new(name=light_name, type='POINT')
            light_data.distance = light_cfg["range"]
            light_data.energy = 0.20
            light_data.color = (light_cfg["r"], light_cfg["g"], light_cfg["b"])
            light_data["cfg_type"] = "maplight"

            light_object = bpy.data.objects.new(name=light_name, object_data=light_data)

            bpy.context.scene.objects.link(light_object)
            if collection is not None:
                collection.objects.link(light_object)

        else:
            light_data = bpy.data.lights.new(name=light_name, type='POINT')
            light_data.energy = light_cfg["range"] * 50.0
            light_data.color = (light_cfg["r"], light_cfg["g"], light_cfg["b"])
            light_data.shadow_soft_size = 0.3
            light_data["cfg_type"] = "maplight"

            light_object = bpy.data.objects.new(name=light_name, object_data=light_data)

            collection.objects.link(light_object)

        blender_objs.append(light_object)
        # light_object.parent = blender_obj

        # Change light position
        light_object.location = (light_cfg["x"], light_cfg["y"], light_cfg["z"])

    # Create lens flares
    flares = cfg_data.get("light_flares", [])
    for flare_ind, flare in enumerate(flares):
        flare_name = "::light_enh{0}_{1}".format("" if flare["type"] == "[light_enh]" else "_2", flare_ind)
        flare_obj = bpy.data.objects.new(flare_name, None)
        if bpy.app.version < (2, 80):
            bpy.context.scene.objects.link(flare_obj)
            if collection is not None:
                collection.objects.link(flare_obj)

            flare_obj.empty_draw_size = flare["size"]
            flare_obj.empty_draw_type = "IMAGE"
        else:
            collection.objects.link(flare_obj)

            flare_obj.empty_display_size = flare["size"]
            flare_obj.empty_display_type = "IMAGE"
            flare_obj.use_empty_image_alpha = True

        flare_obj.empty_image_offset = (-0.5, -0.5)
        flare_obj.color = (flare["col_r"], flare["col_g"], flare["col_b"], 0.5)
        # flare_obj.parent = blender_obj
        flare_obj.location = (flare["x_pos"], flare["y_pos"], flare["z_pos"])
        flare_obj.rotation_euler = (-math.pi / 2, 0, 0)

        if "texture" in flare and flare["texture"] != "":
            tex_path = flare["texture"]
        else:
            tex_path = "licht.bmp"
        image = load_image(filepath, tex_path)
        flare_obj.data = image

        # Copy across all the parameters' blender can't render...
        flare_obj["type"] = flare["type"]
        if flare["type"] == "[light_enh_2]":
            flare_obj["forward_vector"] = (flare["x_fwd"], flare["y_fwd"], flare["z_fwd"])
            flare_obj["rotation_axis"] = (flare["x_rot"], flare["y_rot"], flare["z_rot"])
            flare_obj["omnidirectional"] = flare["omni"]
            flare_obj["rotating"] = flare["rotating"]
            flare_obj["max_brightness_angle"] = flare["max_brightness_angle"]
            flare_obj["min_brightness_angle"] = flare["min_brightness_angle"]
            flare_obj["cone_effect"] = flare["cone_effect"]
        flare_obj["brightness_var"] = flare["brightness_var"]
        flare_obj["brightness"] = flare["brightness"]
        flare_obj["z_offset"] = flare["z_offset"]
        flare_obj["effect"] = flare["effect"]
        flare_obj["ramp_time"] = flare["ramp_time"]

        blender_objs.append(flare_obj)


def load_o3d(object_directory, path_to_file, split_normals):
    """
    Imports an o3d file and creates a Blender mesh for it.
    :param object_directory: path to the root directory of the model
    :param path_to_file: path to the o3d file to load
    :return:
    """
    try:
        with open(path_to_file, "rb") as f:
            o3d_bytes = f.read()
    except IOError:
        log("WARNING: Couldn't open {0}!".format(path_to_file))
        return [], [], None, None, None

    o3d = o3dconvert.import_o3d(o3d_bytes)
    verts = o3d[1]
    edges = []
    faces = o3d[2]

    mesh = bpy.data.meshes.new(name=path_to_file[len(object_directory):-4])

    vertex_pos = [x[0] for x in verts]
    normals = [x[1] for x in verts]  # [(x[1][0], x[1][2], x[1][1]) for x in verts]
    uvs = [(x[2][0], 1 - x[2][1]) for x in verts]
    face_list = [x[0] for x in faces]
    matl_ids = [x[1] for x in faces]
    materials = o3d[3]

    mesh.from_pydata(vertex_pos, edges, face_list)

    if bpy.app.version < (2, 80):
        mesh.uv_textures.new("UV Map")
    else:
        mesh.uv_layers.new(name="UV Map")

    axis_conversion_matrix = Matrix((
        (1, 0, 0, 0),
        (0, 0, 1, 0),
        (0, 1, 0, 0),
        (0, 0, 0, 1)
    ))
    # log("Imported matrix (pre-rounding): \n{0}".format(o3d[5]))
    o3d_transform = [tuple(0 if -1e-7 < x < 1e-7 else x for x in y) for y in o3d[5]]
    o3d_transform_matrix = Matrix(o3d_transform)
    o3d_transform_matrix.transpose()
    # log("Imported matrix: \n{0}".format(o3d_transform_matrix))
    if bpy.app.version < (2, 80):
        o3d_transform_matrix = axis_conversion_matrix * o3d_transform_matrix * axis_conversion_matrix
        i_o3d_transform_matrix = o3d_transform_matrix.inverted()
        mesh_matrix = i_o3d_transform_matrix * axis_conversion_matrix
    else:
        o3d_transform_matrix = axis_conversion_matrix @ o3d_transform_matrix @ axis_conversion_matrix
        i_o3d_transform_matrix = o3d_transform_matrix.inverted()
        mesh_matrix = i_o3d_transform_matrix @ axis_conversion_matrix
    # log("Converted matrix: \n{0}".format(o3d_transform_matrix))
    # log("Inverted matrix: \n{0}".format(i_o3d_transform_matrix))
    # log("Mesh matrix: \n{0}".format(mesh_matrix))

    if split_normals:
        mesh.create_normals_split()
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        mesh.normals_split_custom_set_from_vertices(normals)
        mesh.use_auto_smooth = True
    else:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))

    if bpy.app.version < (2, 80):
        mesh.update(calc_tessface=True)
        mesh.calc_normals_split()
    else:
        mesh.update()
        mesh.calc_loop_triangles()
        mesh.calc_normals_split()

    mesh.validate(verbose=False, clean_customdata=True)

    mesh.transform(mesh_matrix)
    if mesh_matrix.is_negative:
        mesh.flip_normals()

    for face in mesh.polygons:
        for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
            mesh.uv_layers[0].data[loop_idx].uv = uvs[vert_idx]

    return materials, matl_ids, mesh, o3d, o3d_transform_matrix


def generate_materials(cfg_materials, cfg_file_path, mat_counter, materials, mesh):
    """
    Generates Blender materials for an o3d file.

    :param cfg_materials: the material dictionary for this particular mesh as defined in the model.cfg file
    :param cfg_file_path: the path to the model.cfg file
    :param mat_counter: the global material counter
    :param materials: the o3d material definition
    :param mesh: the Blender mesh to generate materials for
    :return: the new global material counter
    """

    # Create materials
    for matl in materials:
        # log(matl)
        diffuse_r = matl[0][0]
        diffuse_g = matl[0][1]
        diffuse_b = matl[0][2]
        diffuse_a = matl[0][3]
        spec_r = matl[1][0]
        spec_g = matl[1][1]
        spec_b = matl[1][2]
        emit_r = matl[2][0]
        emit_g = matl[2][0]
        emit_b = matl[2][0]
        spec_h = matl[3]

        mat_blender = bpy.data.materials.new("{0}-{1}".format(matl[4], str(mat_counter)))
        if bpy.app.version < (2, 80):
            mat = mat_blender
            mat.diffuse_color = (diffuse_r, diffuse_g, diffuse_b)
            mat.diffuse_intensity = 1
            mat.specular_hardness = spec_h
            mat.specular_intensity = 0
            mat.specular_color = (spec_r, spec_g, spec_b)
            mat.emit = np.mean(np.array(matl[2]) / np.max((np.array(matl[0][:3]), np.repeat(0.0001, 3)), axis=0))
        else:
            mat_blender.use_nodes = True
            mat = o3d_node_shader_utils.PrincipledBSDFWrapper(mat_blender, is_readonly=False)
            mat.base_color = (diffuse_r, diffuse_g, diffuse_b)
            mat.specular = spec_r * 0
            mat.roughness = 1 - spec_h
            # TODO: Specular tint doesn't support colour, find a solution
            mat.specular_tint = 0  # (spec_r, spec_g, spec_b)

            mat_blender.use_backface_culling = True
            mat_blender.blend_method = "HASHED"
            mat_blender.shadow_method = "HASHED"

        # Load the diffuse texture and assign it to a new texture slot
        diff_tex = load_texture_into_new_slot(cfg_file_path, matl[4], mat)
        if diff_tex:
            if bpy.app.version >= (2, 80):
                mat.base_color_texture.image = diff_tex.texture.image

            # In some versions of Blender the colourspace isn't correctly detected, force it to sRGB for diffuse
            diff_tex.texture.image.colorspace_settings.name = 'sRGB'
            diff_tex.texture.image.alpha_mode = "NONE"
            # Read the material config to see if we need to apply transparency
            key = matl[4].lower()
            # cfg_materials should always contain an entry for the key, but if no [matl] tag is defined it won't
            # have a "diffuse" item
            if key in cfg_materials and "diffuse" in cfg_materials[key]:
                if "alpha" in cfg_materials[key] and cfg_materials[key]["alpha"][0] > 0:
                    # Material uses alpha stored in diffuse texture alpha channel
                    if bpy.app.version < (2, 80):
                        mat.use_transparency = True
                        diff_tex.use_map_alpha = True
                        diff_tex.alpha_factor = 1
                    else:
                        mat.alpha_texture.image = diff_tex.texture.image
                        if cfg_materials[key]["alpha"][0] == 1:
                            mat_blender.blend_method = "CLIP"
                            mat_blender.shadow_method = "CLIP"
                        else:
                            mat_blender.blend_method = "HASHED"
                            mat_blender.shadow_method = "HASHED"

                    mat.alpha = 0

                if "transmap" in cfg_materials[key]:
                    # Material uses dedicated transparency texture
                    if bpy.app.version < (2, 80):
                        diff_tex.use_map_alpha = False
                    else:
                        # Set the specular texture to the alpha channel of the diffuse texture
                        mat.specular_texture.image = diff_tex.texture.image
                    # Load the new transmap
                    trans_map = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["transmap"][0], mat)
                    if trans_map:
                        if bpy.app.version < (2, 80):
                            trans_map.texture.image.use_alpha = False
                            trans_map.use_map_alpha = True
                            trans_map.alpha_factor = 1
                            trans_map.use_map_color_diffuse = False
                        else:
                            mat.alpha_texture.image = trans_map.texture.image
                            mat_blender.blend_method = "HASHED"
                            mat_blender.shadow_method = "HASHED"
                    else:
                        mat.alpha = 1

                if "envmap" in cfg_materials[key]:
                    if bpy.app.version < (2, 80):
                        mat.specular_intensity = cfg_materials[key]["envmap"][0] ** 2
                        mat.specular_hardness = 1 / 0.01
                    else:
                        mat.specular = cfg_materials[key]["envmap"][0] ** 2
                        mat.roughness = 0.01

                    if "envmap_mask" in cfg_materials[key]:
                        # Load the new transmap
                        envmap_mask = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["envmap_mask"][0],
                                                                 mat)
                        if envmap_mask:
                            if bpy.app.version < (2, 80):
                                # TODO: Blender 2.79 compat for envmap masks
                                pass
                            else:
                                # TODO: Doesn't multiply by the envmap strength
                                mat.specular_texture.image = envmap_mask.texture.image

                if "bumpmap" in cfg_materials[key]:
                    if bpy.app.version < (2, 80):
                        # TODO: Blender 2.79 compat for bump maps
                        # mat.specular_intensity = cfg_materials[key]["envmap"][0] ** 2
                        # mat.specular_hardness = 1 / 0.01
                        cfg_materials[key]["cfg_data"].append([
                            "[matl_bumpmap]",
                            cfg_materials[key]["bumpmap"],
                            str(cfg_materials[key]["bumpmap_strength"])
                        ])
                    else:
                        bump = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["bumpmap"][0], mat)
                        if bump is not None:
                            mat.normalmap_texture.is_bump_map = True
                            mat.normalmap_texture.image = bump.texture.image
                            mat.normalmap_strength = cfg_materials[key]["bumpmap_strength"][0]

                if "alphascale" in cfg_materials[key]:
                    # TODO: parameterize the default alphascale value
                    # mat_blender.blend_method = "BLEND"
                    # TODO: alpha_hash doesn't work correctly on  z-intersecting faces (a frequent problem with dirt maps)
                    pass

                if "allcolor" in cfg_materials[key]:
                    # TODO: Work out if this is meant to override the material values or not
                    # TODO: Blender 2.79 compat
                    # Allcolor allows material properties to be set to constant values
                    allcolor = cfg_materials[key]["allcolor"]
                    mat.base_color = [x[0] for x in allcolor[0:3]]
                    mat.alpha = allcolor[3][0]
                    emission = [allcolor[4][0] * 0.1 + allcolor[10][0],
                                allcolor[5][0] * 0.1 + allcolor[11][0],
                                allcolor[6][0] * 0.1 + allcolor[12][0]]
                    mat.emission_color = emission
                    # The allcolor emission values always seem to look bad, for now it's just disabled
                    mat.emission_strength = 0
                    mat.specular = sum([x[0] for x in allcolor[7:10]]) / 3
                    mat.roughness = 1 / max(allcolor[13][0] / 10, 0.1)

                if "nightmap" in cfg_materials[key]:
                    # A nightmap is an emission texture which is automatically toggled at night
                    if bpy.app.version < (2, 80):
                        # TODO: Blender 2.79 compat for nightmaps
                        cfg_materials[key]["cfg_data"].append([
                            "[matl_nightmap]",
                            cfg_materials[key]["nightmap"][0]
                        ])
                        pass
                    else:
                        nightmap = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["nightmap"][0], mat)
                        if nightmap is not None:
                            mat.emission_color_texture.image = nightmap.texture.image
                            # TODO: Parameterise the nightmaps and lightmaps
                            mat.emission_strength = 0.5

                if "lightmap" in cfg_materials[key]:
                    # A lightmap is an emission texture which is controlled by a script_var
                    if bpy.app.version < (2, 80):
                        # TODO: Blender 2.79 compat for lightmaps
                        cfg_materials[key]["cfg_data"].append([
                            "[matl_lightmap]",
                            cfg_materials[key]["lightmap"][0]
                        ])
                        pass
                    else:
                        lightmap = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["lightmap"][0], mat)
                        if lightmap is not None:
                            mat.emission_color_texture.image = lightmap.texture.image
                            mat.emission_strength = 1.5

                # Populate some useful properties
                bpy.data.materials[mat_blender.name]["type"] = cfg_materials[key]["type"]
                # bpy.data.materials[mat_blender.name]["mat_id"] = cfg_materials[key]["mat_id"]
                if cfg_materials[key]["type"] == "[matl_change]":
                    bpy.data.materials[mat_blender.name]["change_var"] = cfg_materials[key]["change_var"]
                if "envmap_tex" in cfg_materials[key]:
                    bpy.data.materials[mat_blender.name]["envmap_tex"] = cfg_materials[key]["envmap_tex"]

                # Populate remaining properties
                bpy.data.materials[mat_blender.name]["cfg_data"] = cfg_materials[key].get("cfg_data", {})
                # for prop in cfg_materials[key].keys():
                #     if prop[0] == "[" and prop[-1] == "]":
                #         # This must be an unparsed property, therefore we add it to the custom properties of the mesh
                #         bpy.data.materials[mat_blender.name][prop] = cfg_materials[key][prop]
                #         # log("WARNING: Unsupported material property: " + prop + " used on " + mat_blender.name)
            else:
                pass
                # log("WARNING: Material with texture={0} not found in cfg file!".format(matl[3]))

        mesh.materials.append(mat_blender)
        mat_counter += 1
    return mat_counter
