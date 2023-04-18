# ==============================================================================
#  Copyright (c) 2022 Thomas Mathieson.
# ==============================================================================
import math
import os

import mathutils

import bpy
if bpy.app.version > (2, 80):
    from . import o3d_node_shader_utils


def log(*args):
    print("[O3D_CFG_Parser]", *args)


def read_cfg(filepath, override_text_encoding):
    """
    Reads the CFG file for a mesh and parses relevant information such as materials.

    The `cfg_data` dictionary returned is of the following form:
    ::
        cfg_data = {
            0.06: {
                "SD85\SD85_spiegel.o3d": {
                    "viewpoint": ...
                    "matls": {
                        "SD84-85_03.bmp": {
                            "diffuse": "SD84-85_03.bmp",
                            "envmap": 0.5,
                            "last_line": 4673
                        },
                    }
                }
            },
        }

    :param filepath: Path to the CFG file to parse
    :param override_text_encoding: the text encoding to use to read the file instead of utf8/cp1252
    :return: (An array of model file paths (.o3d/.x),
      An array of light entity names,
      The cfg_data dictionary: {lod: {mesh/path: {'matls': {texture_path:{ material properties...}}, mesh properties}}},
      The root folder of the material).
    """
    # get the folder
    folder = (os.path.dirname(filepath))
    if filepath[-3:] == "sco":
        folder += "\\model"

    # log("Loading " + filepath)
    encoding = override_text_encoding if override_text_encoding.strip() != "" else "1252"
    try:
        with open(filepath, 'r', encoding=encoding) as f:
            lines = [l.rstrip() for l in f.readlines()]
    except:
        # Try a different encoding
        with open(filepath, 'r', encoding="utf-8") as f:
            lines = [l.rstrip() for l in f.readlines()]

    cfg_data = {
        -1: {
            "meshes": {},
            "surface": False,
            "cfg_data": []
        }
    }
    files = []
    lights = []

    current_command = None
    current_lod = -1
    current_mat = None
    current_mesh = None
    param_ind = -1
    interior_light_ind = 0
    spotlight_ind = 0
    for i, line in enumerate(lines):
        if len(line) > 2 and line[0] == "[" and line[-1] == "]":
            current_command = line
            param_ind = -1
        else:
            param_ind += 1

        if current_command == "[LOD]":
            if param_ind == 0:
                current_lod = float(line)
                current_mesh = None
                current_mat = None
                cfg_data[current_lod] = {
                    "meshes": {},
                    "surface": False,
                    "cfg_data": []
                }

        elif current_command == "[groups]":
            if param_ind == -1:
                cfg_data[current_lod]["groups"] = {}
            elif param_ind == 0:
                cfg_data[current_lod]["groups"]["ind"] = int(line)
            elif param_ind == 1:
                cfg_data[current_lod]["groups"]["group"] = line

        elif current_command == "[friendlyname]":
            if param_ind == 0:
                cfg_data[current_lod]["friendlyname"] = line

        elif current_command == "[surface]":
            cfg_data[current_lod]["surface"] = True

        elif current_command == "[mesh]":
            if param_ind == 0:
                current_mat = None
                mesh_path = folder + "\\" + line
                if line[-4:] == ".o3d":
                    if os.path.isfile(mesh_path):
                        files.append((mesh_path, current_lod))
                if line[-2:] == ".x":
                    if os.path.isfile(mesh_path):
                        files.append((mesh_path, current_lod))
                current_mesh = line

                cfg_data[current_lod]["meshes"][current_mesh] = {
                    "path": mesh_path,
                    "matls": {},
                    "light_flares": [],
                    "interior_lights": {},
                    "spotlights": {},
                    "cfg_data": []
                }

        # elif current_command == "[viewpoint]":
        #     if param_ind == 0:
        #         cfg_data[current_lod]["meshes"][current_mesh]["viewpoint"] = (int(line), i)

        elif current_command == "[interiorlight]":
            if param_ind == -1:
                interior_light_ind += 1
                cfg_data[current_lod]["meshes"][current_mesh]["interior_lights"][interior_light_ind] = {}

                lights.append(cfg_data[current_lod]["meshes"][current_mesh]["interior_lights"][interior_light_ind])

            m_light = cfg_data[current_lod]["meshes"][current_mesh]["interior_lights"][interior_light_ind]
            if param_ind == 0:
                m_light["variable"] = line
            elif param_ind == 1:
                m_light["range"] = float(line)
            elif param_ind == 2:
                m_light["red"] = float(line) / 255
            elif param_ind == 3:
                m_light["green"] = float(line) / 255
            elif param_ind == 4:
                m_light["blue"] = float(line) / 255
            elif param_ind == 5:
                m_light["x_pos"] = float(line)
            elif param_ind == 6:
                m_light["y_pos"] = float(line)
            elif param_ind == 7:
                m_light["z_pos"] = float(line)

        elif current_command == "[spotlight]":
            if param_ind == -1:
                spotlight_ind += 1
                cfg_data[current_lod]["meshes"][current_mesh]["spotlights"][spotlight_ind] = {}

                lights.append(cfg_data[current_lod]["meshes"][current_mesh]["spotlights"][spotlight_ind])

            m_light = cfg_data[current_lod]["meshes"][current_mesh]["spotlights"][spotlight_ind]
            if param_ind == 0:
                m_light["x_pos"] = float(line)
            elif param_ind == 1:
                m_light["y_pos"] = float(line)
            elif param_ind == 2:
                m_light["z_pos"] = float(line)
            elif param_ind == 3:
                m_light["x_fwd"] = float(line)
            elif param_ind == 4:
                m_light["y_fwd"] = float(line)
            elif param_ind == 5:
                m_light["z_fwd"] = float(line)
            elif param_ind == 6:
                m_light["col_r"] = float(line) / 255
            elif param_ind == 7:
                m_light["col_g"] = float(line) / 255
            elif param_ind == 8:
                m_light["col_b"] = float(line) / 255
            elif param_ind == 9:
                m_light["range"] = float(line)
            elif param_ind == 10:
                m_light["inner_angle"] = float(line)
            elif param_ind == 11:
                m_light["outer_angle"] = float(line)

        elif current_command == "[light_enh]":
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["light_flares"].append({"type": "[light_enh]"})
            light_flare = cfg_data[current_lod]["meshes"][current_mesh]["light_flares"][-1]
            if param_ind == 0:
                light_flare["x_pos"] = float(line)
            elif param_ind == 1:
                light_flare["y_pos"] = float(line)
            elif param_ind == 2:
                light_flare["z_pos"] = float(line)
            elif param_ind == 3:
                light_flare["col_r"] = float(line) / 255
            elif param_ind == 4:
                light_flare["col_g"] = float(line) / 255
            elif param_ind == 5:
                light_flare["col_b"] = float(line) / 255
            elif param_ind == 6:
                light_flare["size"] = float(line)
            elif param_ind == 7:
                light_flare["brightness_var"] = line
            elif param_ind == 8:
                light_flare["brightness"] = float(line)
            elif param_ind == 9:
                light_flare["z_offset"] = float(line)
            elif param_ind == 10:
                light_flare["effect"] = int(line)
            elif param_ind == 11:
                light_flare["ramp_time"] = float(line)
            elif param_ind == 12:
                light_flare["texture"] = line

        elif current_command == "[light_enh_2]":
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["light_flares"].append({"type": "[light_enh_2]"})
            light_flare = cfg_data[current_lod]["meshes"][current_mesh]["light_flares"][-1]
            if param_ind == 0:
                light_flare["x_pos"] = float(line)
            elif param_ind == 1:
                light_flare["y_pos"] = float(line)
            elif param_ind == 2:
                light_flare["z_pos"] = float(line)
            elif param_ind == 3:
                light_flare["x_fwd"] = float(line)
            elif param_ind == 4:
                light_flare["y_fwd"] = float(line)
            elif param_ind == 5:
                light_flare["z_fwd"] = float(line)
            elif param_ind == 6:
                light_flare["x_rot"] = float(line)
            elif param_ind == 7:
                light_flare["y_rot"] = float(line)
            elif param_ind == 8:
                light_flare["z_rot"] = float(line)
            elif param_ind == 9:
                light_flare["omni"] = int(line) == 1
            elif param_ind == 10:
                light_flare["rotating"] = int(line)
            elif param_ind == 11:
                light_flare["col_r"] = float(line) / 255
            elif param_ind == 12:
                light_flare["col_g"] = float(line) / 255
            elif param_ind == 13:
                light_flare["col_b"] = float(line) / 255
            elif param_ind == 14:
                light_flare["size"] = float(line)
            elif param_ind == 15:
                light_flare["max_brightness_angle"] = float(line)
            elif param_ind == 16:
                light_flare["min_brightness_angle"] = float(line)
            elif param_ind == 17:
                light_flare["brightness_var"] = line
            elif param_ind == 18:
                light_flare["brightness"] = float(line)
            elif param_ind == 19:
                light_flare["z_offset"] = float(line)
            elif param_ind == 20:
                light_flare["effect"] = int(line)
            elif param_ind == 21:
                light_flare["cone_effect"] = int(line) == 1
            elif param_ind == 22:
                light_flare["ramp_time"] = float(line)
            elif param_ind == 23:
                light_flare["texture"] = line

        elif current_command == "[matl]" or current_command == "[matl_change]":
            if param_ind == 0:
                matl = line.lower()
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][matl] = {
                    "diffuse": (line, i),
                    "type": current_command,
                    "cfg_data": []
                }
                current_mat = matl
            elif param_ind == 1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["mat_id"] = int(line)
            elif current_command == "[matl_change]" and param_ind == 2:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["change_var"] = line

        elif current_command == "[matl_alpha]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == 0:
                try:
                    cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["alpha"] = (int(line), i)
                except ValueError:
                    log("Found matl_alpha tag with invalid parameter! Line=" + str(i))

        elif current_command == "[matl_transmap]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == 0:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["transmap"] = (line, i)

        elif current_command == "[matl_envmap]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            # TODO: Load the actual transmap
            if param_ind == 0:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["envmap_tex"] = line
            if param_ind == 1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["envmap"] = (float(line), i)

        elif current_command == "[matl_envmap_mask]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == 0:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["envmap_mask"] = (line, i)

        elif current_command == "[matl_bumpmap]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == 0:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["bumpmap"] = (line, i)
            if param_ind == 1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["bumpmap_strength"] = (
                    float(line), i)

        elif current_command == "[alphascale]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == 0:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["alphascale"] = (line, i)

            # alphascale is not currently exported correctly, so we'll re-add it to the cfg_data as an unparsed command
            # so that it re-exports correctly
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command] = []
            else:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command].append(line)

        elif current_command == "[matl_noZwrite]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["noZwrite"] = True

            # alphascale is not currently exported correctly, so we'll re-add it to the cfg_data as an unparsed command
            # so that it re-exports correctly
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command] = []
            else:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command].append(line)

        elif current_command == "[matl_noZcheck]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["noZcheck"] = True

            # alphascale is not currently exported correctly, so we'll re-add it to the cfg_data as an unparsed command
            # so that it re-exports correctly
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command] = []
            else:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command].append(line)

        elif current_command == "[matl_allcolor]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["allcolor"] = []
            elif param_ind < 14:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["allcolor"].append((float(line), i))

            # Allcolor is not currently exported correctly, so we'll re-add it to the cfg_data as an unparsed command
            # so that it re-exports correctly
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command] = []
            else:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat][current_command].append(line)

        elif current_command == "[matl_nightmap]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == 0:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["nightmap"] = (line, i)

        elif current_command == "[matl_lightmap]":
            if current_mat is None:
                log("Invalid command {0} at line {1}! Must precede a [matl] command!".format(current_command, i))
                continue

            if param_ind == 0:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["lightmap"] = (line, i)

        # Unused commands are parsed and stored in the cfg_data dictionary, but they keep their square brackets so they
        # can be differentiated later.
        elif current_mat is not None:
            # Current command is not currently parsed
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["cfg_data"].append([current_command])
            else:
                cfg_data[current_lod]["meshes"][current_mesh]["matls"][current_mat]["cfg_data"][-1].append(line)

        elif current_mesh is not None:
            # Current command is not currently parsed
            if param_ind == -1:
                cfg_data[current_lod]["meshes"][current_mesh]["cfg_data"].append([current_command])
            else:
                cfg_data[current_lod]["meshes"][current_mesh]["cfg_data"][-1].append(line)

        elif current_lod is not None and current_command is not None:
            # Current command is not currently parsed
            if param_ind == -1:
                cfg_data[current_lod]["cfg_data"].append([current_command])
            else:
                cfg_data[current_lod]["cfg_data"][-1].append(line)

    return cfg_data, (folder + "\\")


def write_additional_cfg_props(cfg_props, f):
    if "cfg_data" in cfg_props:
        for prop in cfg_props["cfg_data"]:
            f.write(prop[0] + "\n")
            f.write("\n".join(prop[1:]))
            f.write("\n")

            if len(prop) > 1 and prop[-1].strip() != "":
                f.write("\n")


def write_cfg_mesh(f, filepath, context, obj):
    if "export_path" in obj:
        export_path = obj["export_path"]
    else:
        export_path = obj.name + ".o3d"

    f.write("---------------------------------------------------------------\n"
            "\t\t{0}\n\n".format(export_path[:-4].upper()))
    f.write("[mesh]\n{0}\n\n".format(export_path))

    write_additional_cfg_props(obj.data, f)

    # Materials
    write_cfg_materials(f, obj)


def col_float_to_int(col):
    """
    Converts a Blender colour (rgb in the 0-1 range into the 0-255 (int) range)
    :param col:
    :return:
    """
    return (max(min(int(x*255), 255), 0) for x in col)


def write_cfg_empty(f, filepath, context, obj):
    if "type" not in obj:
        return

    pos = obj.location

    f.write("----------\n")
    if obj["type"] == "[light_enh]":
        texture = os.path.basename(obj.data.filepath)
        if texture == "licht.bmp":
            texture = ""

        if bpy.app.version < (2, 80):
            size = obj.empty_draw_size
        else:
            size = obj.empty_display_size

        f.write("[light_enh]\n")
        f.write("\n".join(map(str, (*pos[:3],
                                    *col_float_to_int(obj.color[:3]),
                                    size,
                                    obj["brightness_var"], obj["brightness"],
                                    obj["z_offset"], obj["effect"], obj["ramp_time"],
                                    texture))))
        f.write("\n\n")
    elif obj["type"] == "[light_enh_2]":
        texture = os.path.basename(obj.data.filepath)
        if texture == "licht.bmp":
            texture = ""

        if bpy.app.version < (2, 80):
            size = obj.empty_draw_size
        else:
            size = obj.empty_display_size

        f.write("[light_enh_2]\n")
        f.write("\n".join(map(str, (*pos[:3],
                                    *obj["forward_vector"],
                                    *obj["rotation_axis"],
                                    1 if obj["omnidirectional"] else 0,
                                    obj["rotating"],
                                    *col_float_to_int(obj.color[:3]),
                                    size,
                                    obj["max_brightness_angle"], obj["min_brightness_angle"],
                                    obj["brightness_var"], obj["brightness"],
                                    obj["z_offset"], obj["effect"], obj["cone_effect"], obj["ramp_time"],
                                    texture))))
        f.write("\n\n")

    write_additional_cfg_props(obj.data, f)


def write_cfg_light(f, filepath, context, obj):
    f.write("----------\n")
    if obj.data.type == "SPOT":
        spot_vec = mathutils.Vector((0, 0, 1))
        eul = mathutils.Euler(obj.rotation_euler, "XYZ")
        spot_vec.rotate(eul)
        spot_vec[2] = -spot_vec[2]
        spot_vec[1] = -spot_vec[1]

        f.write("[spotlight]\n")
        f.write("\n".join(map(str, (*obj.location,
                                    *spot_vec,
                                    *col_float_to_int(obj.data.color[:3]),
                                    obj.data.distance if bpy.app.version < (2, 80) else obj.data.energy / 10,
                                    math.degrees(obj.data.spot_size * obj.data.spot_blend),
                                    math.degrees(obj.data.spot_size)))))
        f.write("\n\n")
    elif obj.data.type == "POINT":
        if "variable" in obj.data:
            light_var = obj.data["variable"]
        else:
            light_var = ""
        f.write("[interiorlight]\n")
        f.write("\n".join(map(str, (light_var,
                                    obj.data.distance if bpy.app.version < (2, 80) else obj.data.energy / 10,
                                    *col_float_to_int(obj.data.color[:3]),
                                    *obj.location))))
        f.write("\n\n")

    write_additional_cfg_props(obj.data, f)


def write_cfg_materials(f, obj):
    for i, mat_blender in enumerate(obj.data.materials):
        mat = o3d_node_shader_utils.PrincipledBSDFWrapper(mat_blender, is_readonly=True)
        if mat.base_color_texture is not None and mat.base_color_texture.image is not None:
            f.write("----------\n")
            if "type" in mat_blender and mat_blender["type"] == "[matl_change]":
                f.write("[matl_change]\n{0}\n{1}\n{2}\n\n".format(
                    os.path.basename(mat.base_color_texture.image.filepath),
                    i,
                    mat_blender["change_var"]))
            else:
                f.write("[matl]\n{0}\n{1}\n\n".format(os.path.basename(mat.base_color_texture.image.filepath), i))

            transmap = False
            alpha_mode = 0
            envmap = False
            specular = 0
            bumpmap = None
            emission_tex = None
            if bpy.app.version < (2, 80):
                for tex in mat_blender.texture_slots:
                    if tex.image.use_map_alpha:
                        alpha_mode = 2
                        # TODO: Blender 2.79 support for alpha clip
                        if not tex.image.use_map_color_diffuse:
                            transmap = True

                if mat_blender.specular_hardness > 20:
                    # Heuristic to determine when we might want to turn on the envmap
                    envmap = True

                specular = math.sqrt(mat_blender.specular_intensity)
            else:
                if mat.alpha_texture.image is not None:
                    alpha_mode = 2
                    if mat_blender.blend_method == "CLIP":
                        alpha_mode = 1

                    if mat.alpha_texture.image.filepath != mat.base_color_texture.image.filepath:
                        transmap = True

                if mat.roughness <= 0.1:
                    envmap = True

                specular = math.sqrt(mat.specular)

                if mat.normalmap_texture is not None and mat.normalmap_texture.image is not None:
                    bumpmap = os.path.basename(mat.normalmap_texture.image.filepath)

                if mat.emission_color_texture is not None and mat.emission_color_texture.image is not None:
                    emission_tex = os.path.basename(mat.emission_color_texture.image.filepath)

            if alpha_mode > 0:
                f.write("[matl_alpha]\n{0}\n\n".format(alpha_mode))

            if transmap:
                f.write("[matl_transmap]\n{0}\n\n".format(os.path.basename(mat.alpha_texture.image.filepath)))

            if envmap and specular > 0.01:
                envmap_tex = "envmap.bmp"
                if "envmap_tex" in mat_blender:
                    envmap_tex = mat_blender["envmap_tex"]

                f.write("[matl_envmap]\n{0}\n{1}\n\n".format(envmap_tex, specular))

                if bpy.app.version > (2, 79):
                    if not transmap and mat.specular_texture is not None and mat.specular_texture.image is not None:
                        f.write(
                            "[matl_envmap_mask]\n{0}\n\n".format(os.path.basename(mat.specular_texture.image.filepath)))

            if bumpmap is not None:
                f.write("[matl_bumpmap]\n{0}\n{1}\n\n".format(bumpmap, mat.normalmap_strength))

            if emission_tex is not None:
                # Again, this is a bit of a rubbish heuristic, it should be improved at some point
                if mat.emission_strength > 1:
                    f.write("[matl_lightmap]\n{0}\n\n".format(emission_tex))
                else:
                    f.write("[matl_nightmap]\n{0}\n\n".format(emission_tex))

            write_additional_cfg_props(mat_blender, f)


def write_cfg_object(context, f, filepath, obj):
    o_type = obj.type
    if o_type == "MESH":
        write_cfg_mesh(f, filepath, context, obj)
    elif o_type == "LIGHT":
        write_cfg_light(f, filepath, context, obj)
    elif o_type == "LAMP":
        write_cfg_light(f, filepath, context, obj)
    elif o_type == "EMPTY":
        write_cfg_empty(f, filepath, context, obj)
    else:
        log("Unsupported object type for export: {0} for {1}".format(obj.type, obj.name))


def write_cfg(filepath, objs, context, selection_only):
    """
    Attempts to merge blender objects into an existing CFG/SCO file
    :param selection_only: whether to only export selected objects
    :param context: the current Blender context
    :param filepath: path to the cfg file, if it doesn't exist a new one will be created
    :param objs: [Deprecated] the array of Blender objects to export
    :return:
    """

    if True or not os.path.isfile(filepath):
        with open(filepath, "w") as f:
            log("Writing cfg file...")
            scene = bpy.data.scenes[context.scene.name]
            if "groups" not in scene:
                scene["groups"] = {
                    "ind": 1,
                    "group": "BlenderExport"
                }
            if "friendlyname" not in scene:
                scene["friendlyname"] = os.path.basename(filepath)[:-4]

            # Create a new minimal CFG file
            f.write("""
###############################################################
# GENERATED BY BLENDER-O3D-IO COPYRIGHT THOMAS MATHIESON 2023 #
###############################################################

[groups]
{0}
{1}

[friendlyname]
{2}
    
""".format(scene["groups"]["ind"], scene["groups"]["group"], scene["friendlyname"]))

            # Populate any cfg data in the scene
            write_additional_cfg_props(scene, f)

            f.write("\n###############################################################\n"
                    "\t\tBEGIN MODEL DATA\n"
                    "###############################################################\n\n")

            # Now write each lod and each mesh within those lods
            if bpy.app.version < (2, 80):
                group_names = [x.name for x in bpy.data.groups]
                lods = [(x, float(x[4:])) for x in group_names if x.startswith("LOD")]
                lods = sorted(lods, key=lambda x: x[1], reverse=True)
                non_lods = [o for x in group_names for o in bpy.data.groups[x].objects if
                            not x.startswith("LOD")]

                non_lods.extend(context.scene.objects)
            else:
                collection_names = [x.name for x in bpy.data.collections]
                lods = [(x, float(x[4:])) for x in collection_names if x.startswith("LOD")]
                lods = sorted(lods, key=lambda x: x[1], reverse=True)
                non_lods = [o for x in collection_names for o in bpy.data.collections[x].all_objects if
                            not x.startswith("LOD")]

                non_lods.extend(context.scene.collection.objects)

            for obj in non_lods:
                if selection_only:
                    if bpy.app.version > (2, 80):
                        if not obj.select_get():
                            continue
                    else:
                        if not obj.select:
                            continue

                # log("Exporting {0}...".format(obj.name))
                write_cfg_object(context, f, filepath, obj)

            for lod in lods:
                f.write("\n###############################################################\n"
                        "\t\tBEGIN LOD {0}\n"
                        "###############################################################\n\n".format(lod[1]))
                f.write("[LOD]\n{0}\n\n".format(lod[1]))

                if bpy.app.version < (2, 80):
                    objs = bpy.data.groups[lod[0]].objects
                else:
                    objs = bpy.data.collections[lod[0]].all_objects

                for obj in objs:
                    if selection_only:
                        if bpy.app.version > (2, 80):
                            if not obj.select_get():
                                continue
                        else:
                            if not obj.select:
                                continue

                    # log("Exporting {0}...".format(obj.name))
                    write_cfg_object(context, f, filepath, obj)
