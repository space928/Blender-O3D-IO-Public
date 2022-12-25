# ==============================================================================
#  Copyright (c) 2022 Thomas Mathieson.
# ==============================================================================

import time
from math import radians

import bpy
import os

if not (bpy.app.version[0] < 3 and bpy.app.version[1] < 80):
    from bpy_extras import node_shader_utils
from . import o3dconvert

# from . import log
from mathutils import Matrix
from .o3d_cfg_parser import read_cfg


def log(*args):
    print("[O3D_Import]", *args)


class TextureSlotWrapper:
    """
    Wrapper around old texture slot type
    """

    class TextureWrapper:
        """
        Wrapper around old texture type
        """

        def __init__(self, image):
            self.image = image

    def __init__(self, image):
        self.texture = TextureSlotWrapper.TextureWrapper(image)


def load_texture_into_new_slot(base_file_path, texture_path, mat):
    if base_file_path[-3:] == "sco":
        tex_file = os.path.dirname(base_file_path) + "\\texture\\" + texture_path.lower()
    else:
        tex_file = os.path.dirname(base_file_path) + "\\..\\texture\\" + texture_path.lower()
    pre, ext = os.path.splitext(tex_file)
    if os.path.isfile(pre + ".dds"):
        tex_file = pre + ".dds"
    if os.path.isfile(tex_file):
        # TODO: Alpha_8_UNORM DDS files are not supported by Blender
        image = bpy.data.images.load(tex_file,
                                     check_existing=True)
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            tex = bpy.data.textures.new(texture_path, type="IMAGE")
            tex.type_recast()
            tex.image = image
            texs = mat.texture_slots.add()
            texs.texture = tex
            return texs
        else:
            # Wrapper around old texture type
            return TextureSlotWrapper(image)
    return None


dbg_unrecognised_commands = set()


def do_import(filepath, context):
    """
    Imports the selected CFG/SCO/O3D file
    :param filepath: the path to the file to import
    :param context: blender context
    :return: success message
    """
    obj_root = os.path.dirname(filepath)
    start_time = time.time()
    if filepath[-3:] == "o3d":
        files = [(filepath, (0, 0))]
        cfg_materials = {}
        lights = []
    else:
        (files, lights, cfg_materials, obj_root) = read_cfg(filepath)

    bpy.context.window_manager.progress_begin(0, len(files))

    # Iterate through the selected files
    blender_objs = []
    mat_counter = 0
    for index, i in enumerate(files):
        # Generate full path to file
        path_to_file = i[0]
        bpy.context.window_manager.progress_update(index)

        if path_to_file[-1:] == "x":
            # X files are not supported by this importer
            try:
                x_file_path = {"name": os.path.basename(path_to_file)}
                # Clunky solution to work out what has been imported because the x importer doesn't set selection
                old_objs = set(context.scene.objects)
                bpy.ops.import_scene.x(filepath=path_to_file, files=[x_file_path], axis_forward='Y', axis_up='Z',
                                       use_split_objects=False, use_split_groups=False)
                # mat_counter = generate_materials(cfg_materials, filepath, mat_counter, materials, mesh, obj_root,
                #                                 path_to_file)
                blender_objs.extend(set(context.scene.objects) - old_objs)
                continue
            except AttributeError:
                log("WARNING: {0} was not imported! No X importer found!".format(path_to_file))

        # Load mesh
        with open(path_to_file, "rb") as f:
            o3d_bytes = f.read()
        log("Loading " + path_to_file + "...")
        o3d = o3dconvert.import_o3d(o3d_bytes)
        verts = o3d[1]
        edges = []
        faces = o3d[2]
        mesh = bpy.data.meshes.new(name=path_to_file[len(obj_root):-4])

        vertex_pos = [x[0] for x in verts]
        normals = [x[1] for x in verts]
        uvs = [(x[2][0], 1-x[2][1]) for x in verts]
        face_list = [x[0] for x in faces]
        matl_ids = [x[1] for x in faces]
        materials = o3d[3]

        mesh.from_pydata(vertex_pos, edges, face_list)
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            mesh.uv_textures.new("UV Map")
        else:
            mesh.uv_layers.new(name="UV Map")

        mx = Matrix.Identity(4)  # Matrix(o3d[5])
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            mx = mx * Matrix.Scale(-1.0, 4, (0.0, 1.0, 0.0)) * Matrix.Rotation(radians(-270.0), 4, 'X')
        else:
            mx = mx @ Matrix.Scale(-1.0, 4, (0.0, 1.0, 0.0)) @ Matrix.Rotation(radians(-270.0), 4, 'X')
        for n, vert in enumerate(mesh.vertices):
            if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                vert.co = mx * vert.co
            else:
                vert.co = mx @ vert.co
            # vert.normal = normals[n]

        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            mesh.update(calc_tessface=True)
        else:
            mesh.update()

        mesh.create_normals_split()
        mesh.use_auto_smooth = True
        mesh.normals_split_custom_set_from_vertices(normals)

        for face in mesh.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                mesh.uv_layers[0].data[loop_idx].uv = uvs[vert_idx]

        # Create object
        blender_obj = None
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            blender_obj = bpy.data.objects.new(path_to_file[len(obj_root):-4], mesh)
            blender_objs.append(blender_obj)
            scene = bpy.context.scene
            scene.objects.link(blender_obj)
            # For objects with LODs (ie: lod != default value of (0, 0)) ad them to a new group
            if i[1] != (0, 0):
                group = bpy.data.groups.new("LOD_{0}_{1}".format(*i[1]))
                bpy.ops.object.group_link(group)
        else:
            blender_obj = bpy.data.objects.new(path_to_file[len(obj_root):-4], mesh)
            blender_objs.append(blender_obj)
            view_layer = context.view_layer
            # For objects with no LODs (ie: lod = default value of (0, 0)) add them to the current collection
            # Otherwise, create a new collection for the LOD
            if i[1] == (0, 0):
                collection = view_layer.active_layer_collection.collection
            else:
                collection_name = "LOD_{0}_{1}".format(*i[1])
                if collection_name not in bpy.data.collections:
                    collection = bpy.data.collections.new(collection_name)
                    bpy.context.scene.collection.children.link(collection)
                else:
                    collection = bpy.data.collections[collection_name]

            collection.objects.link(blender_obj)

        # Generate materials
        mat_counter = generate_materials(cfg_materials, filepath, mat_counter, materials, mesh, obj_root, path_to_file)

        # Populate remaining properties
        key = (path_to_file[len(obj_root):], "null_mat")
        for prop in cfg_materials[key].keys():
            if prop[0] == "[" and prop[-1] == "]":
                # This must be an unparsed property, therefore we add it to the custom properties of the mesh
                bpy.data.meshes[mesh.name][prop] = cfg_materials[key][prop]

        for ind, tri in enumerate(mesh.polygons):
            tri.material_index = matl_ids[ind]

        # mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        mesh.update()

        bpy.ops.object.select_all(action='DESELECT')
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            blender_obj.select = True
        else:
            blender_obj.select_set(True)
        # bpy.ops.object.shade_smooth()
        # bpy.ops.object.mode_set(mode='EDIT')
        # bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

    # Create lights
    for light in lights:
        light_cfg = cfg_materials[light]["light"]

        light_data = bpy.data.lights.new(name=light[0], type='POINT')
        light_data.energy = light_cfg["range"] * 0.4
        light_data.color = (light_cfg["red"], light_cfg["green"], light_cfg["blue"])
        light_data.shadow_soft_size = 0.02
        light_data["variable"] = light_cfg["variable"]

        light_object = bpy.data.objects.new(name=light[0], object_data=light_data)

        bpy.context.collection.objects.link(light_object)

        # Change light position
        light_object.location = (light_cfg["x_pos"], light_cfg["y_pos"], light_cfg["z_pos"])

    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for x in blender_objs:
        x.select_set(True)

    if len(files) == 0:
        log("WARNING: 0 models loaded! File:", filepath)

    # for x in dbg_unrecognised_commands:
    #         log("WARNING: Unrecognised material command in file: " + x)

    log("Loaded {0} models in {1} seconds!".format(len(files), time.time() - start_time))
    return blender_objs


def generate_materials(cfg_materials, cfg_file_path, mat_counter, materials, mesh, obj_root, current_file_path):
    # Create materials
    for matl in materials:
        # log(matl)
        diffuseR = matl[0][0]
        diffuseG = matl[0][1]
        diffuseB = matl[0][2]
        diffuseA = matl[0][3]
        sepcR = matl[1][0]
        sepcG = matl[1][1]
        sepcB = matl[1][2]
        specI = matl[2]
        specH = matl[2] / 1000 * 510 + 1
        # matls.append(())

        # if bpy.data.materials.get("{0}".format(matl[7])) is None:
        mat_blender = bpy.data.materials.new("{0}-{1}".format(matl[3], str(mat_counter)))
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            mat = mat_blender
            mat.diffuse_color = (diffuseR, diffuseG, diffuseB)
            mat.specular_hardness = specH
            mat.specular_intensity = sepcR * 0
            mat.specular_color = (sepcR, sepcG, sepcB)
        else:
            mat_blender.use_nodes = True
            mat = node_shader_utils.PrincipledBSDFWrapper(mat_blender, is_readonly=False)
            mat.base_color = (diffuseR, diffuseG, diffuseB)
            mat.specular = sepcR * 0
            mat.roughness = 1 - specH
            # TODO: Specular tint doesn't support colour, find a solution
            mat.specular_tint = 0  # (sepcR, sepcG, sepcB)

        # Load the diffuse texture and assign it to a new texture slot
        diff_tex = load_texture_into_new_slot(cfg_file_path, matl[3], mat)
        if diff_tex:
            if not (bpy.app.version[0] < 3 and bpy.app.version[1] < 80):
                mat.base_color_texture.image = diff_tex.texture.image

            # In some versions of Blender the colourspace isn't correctly detected, force it to sRGB for diffuse
            diff_tex.texture.image.colorspace_settings.name = 'sRGB'
            # Read the material config to see if we need to apply transparency
            key = (current_file_path[len(obj_root):], matl[3].lower())
            # cfg_materials should always contain an entry for the key, but if no [matl] tag is defined it won't
            # have a "diffuse" item
            if key in cfg_materials and "diffuse" in cfg_materials[key]:
                if "alpha" in cfg_materials[key] and cfg_materials[key]["alpha"][0] > 0:
                    # Material uses alpha stored in diffuse texture alpha channel
                    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                        mat.use_transparency = True
                        diff_tex.use_map_alpha = True
                        diff_tex.alpha_factor = 1
                    else:
                        mat.alpha_texture.image = diff_tex.texture.image

                    mat.alpha = 0
                if "transmap" in cfg_materials[key]:
                    # Material uses dedicated transparency texture
                    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                        diff_tex.use_map_alpha = False
                    # Set the specular texture to the alpha channel of the diffuse texture
                    mat.specular_texture.image = diff_tex.texture.image
                    # Load the new transmap
                    trans_map = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["transmap"][0], mat)
                    if trans_map:
                        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                            trans_map.texture.image.use_alpha = False
                            trans_map.use_map_alpha = True
                            trans_map.alpha_factor = 1
                            trans_map.use_map_color_diffuse = False
                        else:
                            mat.alpha_texture.image = trans_map.texture.image
                    else:
                        # if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                        #     diff_tex.use_map_alpha = True
                        # else:
                        #     mat.alpha_texture.image = diff_tex.texture.image

                        mat.alpha = 1
                if "envmap" in cfg_materials[key]:
                    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                        mat.specular_intensity = cfg_materials[key]["envmap"][0] ** 2
                        mat.specular_hardness = 1 / 0.01
                    else:
                        mat.specular = cfg_materials[key]["envmap"][0] ** 2
                        mat.roughness = 0.01

                    if "envmap_mask" in cfg_materials[key]:
                        # Load the new transmap
                        envmap_mask = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["envmap_mask"][0], mat)
                        if envmap_mask:
                            if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                                # TODO: Blender 2.79 compat for envmap masks
                                pass
                            else:
                                # TODO: Doesn't multiply by the envmap strength
                                mat.specular_texture.image = envmap_mask.texture.image

                if "bumpmap" in cfg_materials[key]:
                    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                        # TODO: Blender 2.79 compat for bump maps
                        # mat.specular_intensity = cfg_materials[key]["envmap"][0] ** 2
                        # mat.specular_hardness = 1 / 0.01
                        pass
                    else:
                        bump = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["bumpmap"][0], mat)
                        if bump is not None:
                            # TODO: Fix this:
                            # mat.normalmap_texture.is_bump_map = True
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
                    emission = [allcolor[4][0]*0.1 + allcolor[10][0],
                                allcolor[5][0]*0.1 + allcolor[11][0],
                                allcolor[6][0]*0.1 + allcolor[12][0]]
                    mat.emission_color = emission
                    # The allcolor emission values always seem to look bad, for now it's just disabled
                    mat.emission_strength = 0
                    mat.specular = sum([x[0] for x in allcolor[7:10]])/3
                    mat.roughness = 1/max(allcolor[13][0]/10, 0.1)

                if "nightmap" in cfg_materials[key]:
                    # A nightmap is an emission texture which is automatically toggled at night
                    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                        # TODO: Blender 2.79 compat for nightmaps
                        pass
                    else:
                        nightmap = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["nightmap"][0], mat)
                        if nightmap is not None:
                            mat.emission_color_texture.image = nightmap.texture.image
                            # TODO: Parameterise the nightmaps and lightmaps
                            mat.emission_strength = 0.5

                if "lightmap" in cfg_materials[key]:
                    # A lightmap is an emission texture which is controlled by a script_var
                    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
                        # TODO: Blender 2.79 compat for lightmaps
                        pass
                    else:
                        lightmap = load_texture_into_new_slot(cfg_file_path, cfg_materials[key]["lightmap"][0], mat)
                        if lightmap is not None:
                            mat.emission_color_texture.image = lightmap.texture.image
                            mat.emission_strength = 1.5

                # Populate remaining properties
                for prop in cfg_materials[key].keys():
                    if prop[0] == "[" and prop[-1] == "]":
                        # This must be an unparsed property, therefore we add it to the custom properties of the mesh
                        dbg_unrecognised_commands.add(prop)
                        # bpy.data.materials[mat_blender.name][prop] = cfg_materials[key][prop]
                        # log("WARNING: Unsupported material property: " + prop + " used on " + mat_blender.name)
            else:
                pass
                # log("WARNING: Material with texture={0} not found in cfg file!".format(matl[3]))

        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            pass
        else:
            mat_blender.use_backface_culling = True
            mat_blender.blend_method = "HASHED"
            mat_blender.shadow_method = "HASHED"

        mesh.materials.append(mat_blender)
        mat_counter += 1
    return mat_counter
