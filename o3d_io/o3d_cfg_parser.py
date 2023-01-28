# ==============================================================================
#  Copyright (c) 2022 Thomas Mathieson.
# ==============================================================================

import os


def log(*args):
    print("[O3D_CFG_Parser]", *args)


def read_cfg(filepath):
    """
    Reads the CFG file for a mesh and parses relevant information such as materials.

    The `cfg_data` dictionary returned is of the following form:
    ::
        cfg_data = {
            ("SD85\SD85_spiegel.o3d", "SD84-85_03.bmp"): {
                "diffuse": "SD84-85_03.bmp",
                "envmap": 0.5,
                "last_line": 4673
            }
        }

    :param filepath: Path to the CFG file to parse
    :return: (An array of model file paths (.o3d/.x),
      An array of light entity names,
      The cfg_data dictionary: key=(mesh_path, diffuse_texture_path) value=dictionary describing the material),
      The root folder of the material).
    """
    # get the folder
    folder = (os.path.dirname(filepath))
    if filepath[-3:] == "sco":
        folder += "\\model"

    # log("Loading " + filepath)
    try:
        with open(filepath, 'r', encoding="1252") as f:
            lines = [l.rstrip() for l in f.readlines()]
    except:
        # Try a different encoding
        with open(filepath, 'r', encoding="utf-8") as f:
            lines = [l.rstrip() for l in f.readlines()]

    cfg_data = {}
    files = []
    lights = []

    current_command = None
    current_lod = (0, 0)
    current_viewpoint = (0, 0)
    current_mat = "null_mat"
    current_mesh = None
    is_surface_sco = False
    param_ind = -1
    light_ind = 0
    for i, line in enumerate(lines):
        if len(line) > 2 and line[0] == "[" and line[-1] == "]":
            current_command = line
            param_ind = -1
        else:
            param_ind += 1

        if current_command == "[surface]":
            is_surface_sco = True

        if current_command == "[LOD]":
            if param_ind == 0:
                current_lod = (float(line), i)

        elif current_command == "[viewpoint]":
            if param_ind == 0:
                current_viewpoint = (int(line), i)

        elif current_command == "[mesh]":
            if param_ind == 0:
                mesh_path = folder + "\\" + line
                if line[-4:] == ".o3d":
                    if os.path.isfile(mesh_path):
                        files.append((mesh_path, current_lod))
                if line[-2:] == ".x":
                    if os.path.isfile(mesh_path):
                        files.append((mesh_path, current_lod))
                current_mesh = line

                # Setup a dummy material entry for per-mesh properties
                current_mat = "null_mat"
                # Needed by the exporter
                # cfg_data[(current_mesh, line)] = {"last_line": i}
                cfg_data[(current_mesh, current_mat)] = {}
                cfg_data[(current_mesh, current_mat)]["LOD"] = current_lod
                cfg_data[(current_mesh, current_mat)]["viewpoint"] = current_viewpoint
                cfg_data[(current_mesh, current_mat)]["[surface]"] = is_surface_sco

        elif current_command == "[interiorlight]":
            if param_ind == -1:
                current_mesh = "::light_{0}".format(light_ind)
                light_ind += 1
                # Setup a dummy material entry for per-mesh properties
                current_mat = "null_mat"
                # Needed by the exporter
                # cfg_data[(current_mesh, line)] = {"last_line": i}
                cfg_data[(current_mesh, current_mat)] = {}
                cfg_data[(current_mesh, current_mat)]["LOD"] = current_lod
                cfg_data[(current_mesh, current_mat)]["viewpoint"] = current_viewpoint
                cfg_data[(current_mesh, current_mat)]["light"] = {}

                lights.append((current_mesh, current_mat))

            if param_ind == 0:
                cfg_data[(current_mesh, current_mat)]["light"]["variable"] = line
            elif param_ind == 1:
                cfg_data[(current_mesh, current_mat)]["light"]["range"] = float(line)
            elif param_ind == 2:
                cfg_data[(current_mesh, current_mat)]["light"]["red"] = float(line)
            elif param_ind == 3:
                cfg_data[(current_mesh, current_mat)]["light"]["green"] = float(line)
            elif param_ind == 4:
                cfg_data[(current_mesh, current_mat)]["light"]["blue"] = float(line)
            elif param_ind == 5:
                cfg_data[(current_mesh, current_mat)]["light"]["x_pos"] = float(line)
            elif param_ind == 6:
                cfg_data[(current_mesh, current_mat)]["light"]["y_pos"] = float(line)
            elif param_ind == 7:
                cfg_data[(current_mesh, current_mat)]["light"]["z_pos"] = float(line)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl]" or current_command == "[matl_change]":
            if param_ind == 0:
                matl = line.lower()
                cfg_data[(current_mesh, matl)] = {}
                cfg_data[(current_mesh, matl)]["diffuse"] = (line, i)
                current_mat = matl
            if param_ind == 1:
                # Last line is used by the exporter to determine where to insert new material properties in the file
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_alpha]":
            if param_ind == 0:
                try:
                    cfg_data[(current_mesh, current_mat)]["alpha"] = (int(line), i)
                except ValueError:
                    log("Found matl_alpha tag with invalid parameter! Line=" + str(i))

                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_transmap]":
            if param_ind == 0:
                cfg_data[(current_mesh, current_mat)]["transmap"] = (line, i)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_envmap]":
            # TODO: Load the actual transmap
            if param_ind == 1:
                cfg_data[(current_mesh, current_mat)]["envmap"] = (float(line), i)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_envmap_mask]":
            if param_ind == 0:
                cfg_data[(current_mesh, current_mat)]["envmap_mask"] = (line, i)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_bumpmap]":
            if param_ind == 0:
                cfg_data[(current_mesh, current_mat)]["bumpmap"] = (line, i)
            if param_ind == 1:
                cfg_data[(current_mesh, current_mat)]["bumpmap_strength"] = (float(line), i)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[alphascale]":
            if param_ind == 0:
                cfg_data[(current_mesh, current_mat)]["alphascale"] = (line, i)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_noZwrite]":
            if param_ind == -1:
                cfg_data[(current_mesh, current_mat)]["noZwrite"] = True
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_noZcheck]":
            if param_ind == -1:
                cfg_data[(current_mesh, current_mat)]["noZcheck"] = True
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_allcolor]":
            if param_ind == -1:
                cfg_data[(current_mesh, current_mat)]["allcolor"] = []
            elif param_ind < 14:
                cfg_data[(current_mesh, current_mat)]["allcolor"].append((float(line), i))

            if param_ind == 13:
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_nightmap]":
            if param_ind == 0:
                cfg_data[(current_mesh, current_mat)]["nightmap"] = (line, i)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_command == "[matl_lightmap]":
            if param_ind == 0:
                cfg_data[(current_mesh, current_mat)]["lightmap"] = (line, i)
                cfg_data[(current_mesh, current_mat)]["last_line"] = i

        elif current_mesh is not None:
            # Current command is not currently parsed
            if param_ind == -1:
                cfg_data[(current_mesh, current_mat)][current_command] = []
            if param_ind >= 0:
                cfg_data[(current_mesh, current_mat)][current_command].append(line)

    return files, lights, cfg_data, (folder + "\\")


def blender_mat_2_cfg_material(obj):
    """
    Converts a blender material into a cfg_material dictionary as used by the importer
    :param obj: object to convert
    :return: a cfg_material dictionary of the form:
    {
        "diffuse":("diffuse_tex", line_number),
        "alpha":(alpha_mode, line_number),
        "transmap":("transmap_tex", line_number),
        "envmap":(envmap_strength, line_number),
    }
    """
    return {}


def cfg_material_prop_2_str(prop, value):
    """
    Converts a cfg_material property item into a string to be used in a CFG file
    :param prop:
    :param value:
    :return: the converted string
    """
    if prop == "diffuse":
        return "\n[matl]\n{0}\n0\n".format(value[0])
    elif prop == "alpha":
        return "\n[matl_alpha]\n{0}\n".format(str(value[0]))
    elif prop == "transmap":
        return "\n[matl_transmap]\n{0}\n".format(value[0])
    elif prop == "envmap":
        return "\n[matl_envmap]\nenvmap.bmp\n{0}\n".format(value[0])
    else:
        log("WARNING: Material property: {0} couldn't be converted to a CFG property!")
        return "\n"


def merge_cfg(filepath, objs):
    """
    Attempts to merge blender objects into an existing CFG/SCO file
    :param filepath: path to the cfg file, if it doesn't exist a new one will be created
    :param objs:
    :return:
    """

    if not os.path.isfile(filepath):
        with open(filepath, "w") as f:
            # Create a new minimal CFG file
            f.write("""
###############################################################
# GENERATED BY BLENDER-O3D-IO COPYRIGHT THOMAS MATHIESON 2022 #
###############################################################

[groups]
1
BlenderExport

[friendlyname]
{0}
""".format(filepath[:-4]))

    # Read what's currently in the CFG file to check if we can update anything
    files, lights, cfg_materials, root_dir = read_cfg(filepath)
    # Convert filepaths to object names (following the convention of the importer)
    files = {str(x[0])[len(root_dir):-4] for x in files}

    log("Skipping CFG merge for now... Not yet implemented...")
    return cfg_materials

    with open(filepath, "r") as f:
        lines = f.readlines()
    inserted_lines = 0
    for o in objs:
        new_cfg_mat = blender_mat_2_cfg_material(o)

        if o.name in files:
            # This object already exists in the CFG, try to update it if necessary
            for prop in new_cfg_mat:
                # TODO: cfg_materials is indexed by the tuple (obj_name, texture_name), this won't work
                if prop in cfg_materials[o.name]:
                    # Two matching properties, update the old one with the new
                    lines[cfg_materials[o.name][prop][1] + inserted_lines] = new_cfg_mat[prop][0]
                else:
                    # Add the new property inside the material
                    if "last_line" not in cfg_materials[o.name]:
                        # If the object only has a [mesh] defined and no material then we won't have the last line cached
                        # Hence we need to search for it
                        # TODO:
                        pass
                    lines.insert(cfg_materials[o.name]["last_line"]+1, cfg_material_prop_2_str(prop, new_cfg_mat[prop]))
                    # TODO: This won't work since new lines can be inserted out of order...
                    inserted_lines += 1
        else:
            # Add a new entry to the CFG for this model file
            lines.append("\n########################################\n"
                         "{0}\n"
                         "########################################\n".format(o.name))
            lines.append("[mesh]\n{0}\n\n".format(o.name + ".o3d"))

            # Write material
            for prop in new_cfg_mat:
                lines.append(cfg_material_prop_2_str(prop, new_cfg_mat[prop]))

    with open(filepath, "w") as f:
        f.writelines(lines)
