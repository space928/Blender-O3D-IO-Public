import math
import os.path
import time

import bpy
import struct

from . import o3d_node_shader_utils, io_omsi_spline
from .blender_texture_io import load_texture_into_new_slot


def log(*args):
    print("[OMSI_Tile_Import]", *args)


def do_import(context, filepath, import_scos, import_splines, spline_tess_dist, spline_tess_angle, import_x):
    # Read global.cfg
    global_cfg = read_cfg_file(os.path.join(os.path.dirname(filepath), "global.cfg"))

    if filepath[-3:] == "map":
        import_tile(context, filepath, import_scos, global_cfg, import_splines, spline_tess_dist, spline_tess_angle,
                    import_x)
    elif filepath[-3:] == "cfg":
        start_time = time.time()
        working_dir = os.path.dirname(filepath)
        objs = []
        tiles = 0
        for map_file in global_cfg["[map]"]:
            x = int(map_file[0])
            y = int(map_file[1])
            path = map_file[2]

            log("### Loading " + path)

            import_tile(context, os.path.join(working_dir, path), import_scos, global_cfg, import_splines,
                        spline_tess_dist, spline_tess_angle, import_x)

            bpy.ops.transform.translate(value=(x * 300, y * 300, 0))

            collection = bpy.data.collections.new(path)
            bpy.context.scene.collection.children.link(collection)

            for o in bpy.context.selected_objects:
                collection.objects.link(o)

            objs.extend(bpy.context.selected_objects)
            bpy.ops.object.select_all(action='DESELECT')
            tiles += 1

        log("### Loaded {0} objects across {1} tiles in {2} seconds!".format(len(objs), tiles,
                                                                             time.time() - start_time))


def import_tile(context, filepath, import_scos, global_cfg, import_splines, spline_tess_dist, spline_tess_angle,
                import_x):
    start_time = time.time()

    map_file = read_cfg_file(filepath)

    # Make terrain mesh
    terrain_obj, terr_heights = import_terrain_mesh(filepath, global_cfg)

    blender_insts = []
    if import_scos:
        blender_insts = import_map_objects(filepath, map_file, terr_heights, import_x)

    if import_splines:
        blender_insts.extend(io_omsi_spline.import_map_splines(filepath, map_file, spline_tess_dist, spline_tess_angle))

    # Make collection
    if bpy.app.version < (2, 80):
        scene = bpy.context.scene
        scene.objects.link(terrain_obj)
    else:
        view_layer = context.view_layer
        collection = view_layer.active_layer_collection.collection
        collection.objects.link(terrain_obj)

    bpy.ops.object.select_all(action='DESELECT')

    if bpy.app.version < (2, 80):
        terrain_obj = True
        bpy.ops.object.shade_smooth()
        for o in blender_insts:
            o.select = True
    else:
        terrain_obj.select_set(True)
        bpy.ops.object.shade_smooth()
        for o in blender_insts:
            o.select_set(True)

    log("Loaded tile {0} in {1} seconds!".format(filepath, time.time() - start_time))


def read_cfg_file(cfg_path):
    with open(cfg_path, 'r', encoding="utf-16-le", errors="replace") as f:
        lines = [l.rstrip() for l in f.readlines()]

    cfg_data = {}

    current_command = None
    param_ind = -1
    for i, line in enumerate(lines):
        if len(line) > 2 and line[0] == "[" and line[-1] == "]":
            current_command = line
            param_ind = -1
        else:
            param_ind += 1

        # if current_command == "[LOD]":
        #     if param_ind == 0:
        #         current_lod = (float(line), i)

        if current_command is not None:
            # Current command is not currently parsed
            if param_ind == -1:
                if current_command in cfg_data:
                    cfg_data[current_command].append([])
                else:
                    cfg_data[current_command] = [[]]
            if param_ind >= 0:
                cfg_data[current_command][-1].append(line)

    return cfg_data


def is_int(x):
    try:
        int(x)
        return True
    except ValueError:
        return False


def generate_terrain_materials(mesh, filepath, global_cfg):
    map_name = os.path.basename(filepath)

    mat_blender = bpy.data.materials.new(filepath)
    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
        mat = mat_blender
        mat.diffuse_color = (0.5, 0.5, .5)
        mat.specular_hardness = 0.1
        mat.specular_intensity = 0.1
        mat.specular_color = (1, 1, 1)

        # TODO: Blender 2.79 compat
        # Remove this once 2.79 compat is done
        mesh.materials.append(mat_blender)
        return
    else:
        mat_blender.use_nodes = True
        mat = o3d_node_shader_utils.LayeredBSDFWrapper(mat_blender, is_readonly=False)
        mat.base_color = (0.5, 0.5, .5)
        mat.specular = 0.1
        mat.roughness = 0.7

    # The base texture has no splat_map, for now we just create a dummy path for it so that it isn't forgotten
    splat_dir = os.path.join(os.path.dirname(filepath), "texture", "map")
    splat_maps = [os.path.join(splat_dir, map_name + ".0.dds")] + \
                 [os.path.join(splat_dir, x) for x in
                  os.listdir(os.path.join(os.path.dirname(filepath), "texture", "map"))
                  if os.path.basename(x).startswith(map_name) and is_int(x[len(map_name) + 1:-4])]

    mat.base_color_n_textures = min(len(splat_maps), 16)

    # Load base texture
    tex = global_cfg["[groundtex]"][0]
    diff_tex = load_texture_into_new_slot(filepath, tex[0], mat)
    if diff_tex:
        mat.base_color_textures[-1][0].image = diff_tex.texture.image
        scale = 1 / float(tex[3])
        mat.base_color_textures[-1][0].scale = (scale, scale, scale)

    # Iterate through all but the first splat_map in reverse
    for i, splat_map in enumerate(splat_maps[:0:-1]):
        f_name = os.path.basename(splat_map)

        tex_no = int(f_name.removeprefix(map_name)[1:-4])

        if i >= 15:
            log("WARNING: Terrain tile has more than 16 textures, only the first 16 will be imported!")
            break

        # TODO: Load detail texture
        tex = global_cfg["[groundtex]"][tex_no]
        diff_tex = load_texture_into_new_slot(filepath, tex[0], mat)
        splat_tex = load_texture_into_new_slot(filepath, splat_map, mat, abs_path=True)
        if diff_tex:
            mat.base_color_textures[i][0].image = diff_tex.texture.image
            scale = 1 / float(tex[3])
            mat.base_color_textures[i][0].scale = (scale, scale, scale)
            if splat_tex and splat_tex.texture.image.has_data:
                mat.base_color_textures[i][1].image = splat_tex.texture.image

    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
        pass
    else:
        mat_blender.use_backface_culling = True

    mesh.materials.append(mat_blender)


def import_terrain_mesh(filepath, global_cfg):
    """
    Imports a terrain mesh from a .terrain file
    :param global_cfg: a dictionary containing the global.cfg file
    :param filepath: path to the .map file
    :return: a blender object of the terrain
    """
    terr_dim = 61
    with open(filepath + ".terrain", "rb") as f:
        # Header
        f.read(0x4)

        # Read heightmap into array
        heights = [[struct.unpack("<f", f.read(4))[0] for x in range(terr_dim)] for y in range(terr_dim)]

    verts = [
        [y * 5, x * 5, heights[x][y]]
        for x in range(terr_dim)
        for y in range(terr_dim)
    ]

    faces = [
        [x * terr_dim + y, x * terr_dim + y + 1,
         (x + 1) * terr_dim + y + 1, (x + 1) * terr_dim + y]
        for x in range(terr_dim - 1)
        for y in range(terr_dim - 1)
    ]

    uvs = [
        (y / (terr_dim - 1), 1 - x / (terr_dim - 1))
        for x in range(terr_dim)
        for y in range(terr_dim)
    ]

    new_mesh = bpy.data.meshes.new("terrain_mesh-" + filepath)
    new_mesh.from_pydata(verts, [], faces)
    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
        new_mesh.uv_textures.new("UV Map")
    else:
        new_mesh.uv_layers.new(name="UV Map")
    new_mesh.update(calc_edges=True)

    for face in new_mesh.polygons:
        for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
            new_mesh.uv_layers[0].data[loop_idx].uv = uvs[vert_idx]

    generate_terrain_materials(new_mesh, filepath, global_cfg)

    # Make object from mesh
    return bpy.data.objects.new("terrain-" + filepath, new_mesh), heights


def lerp(a, b, t):
    return a * t + b * (1 - t)


def clamp_tile(x, dim):
    return max(min(x, dim - 1), 0)


def get_interpolated_height(terr_heights, x, y):
    # Bilinear interpolation of the terrain heightmap
    dim = len(terr_heights)
    x = x / 300 * dim
    y = y / 300 * dim

    x_low = math.floor(x)
    x_high = math.ceil(x)
    x_frac = x - x_low
    y_low = math.floor(y)
    y_high = math.ceil(y)
    y_frac = y - y_low

    x_low = clamp_tile(x_low, dim)
    x_high = clamp_tile(x_high, dim)
    y_low = clamp_tile(y_low, dim)
    y_high = clamp_tile(y_high, dim)

    ll = terr_heights[y_low][x_low]
    lh = terr_heights[y_low][x_high]
    hl = terr_heights[y_high][x_low]
    hh = terr_heights[y_high][x_high]

    il = lerp(ll, hl, x_frac)
    ih = lerp(lh, hh, x_frac)

    return lerp(il, ih, y_frac)


def import_map_objects(filepath, map_file, terr_heights, import_x):
    objs = []
    blender_insts = []

    omsi_dir = os.path.abspath(os.path.join(os.path.dirname(filepath), os.pardir, os.pardir))
    # log("Assuming OMSI directory of: ", omsi_dir)

    if "[object]" not in map_file:
        return blender_insts

    for lines in map_file["[object]"]:
        path = lines[1]
        obj_id = int(lines[2])
        pos = [float(lines[3 + x]) for x in range(3)]
        rot = [float(lines[6 + x]) for x in range(3)]  # ZYX (Z-Up)

        objs.append({"path": os.path.join(omsi_dir, path), "id": obj_id, "pos": pos, "rot": rot})

    log("Loaded {0} objects!".format(len(objs)))

    loaded_objs = {}
    for obj in objs:
        pos = obj["pos"]
        path = obj["path"]
        rot = [-x / 180 * 3.14159265 for x in obj["rot"]]

        if path in loaded_objs:
            # Save time by duplicating existing objects
            if bpy.app.version < (2, 80):
                for o in bpy.context.selected_objects:
                    o.select = False
                for o in loaded_objs[path]:
                    o.select = True
            else:
                for o in bpy.context.selected_objects:
                    o.select_set(False)
                for o in loaded_objs[path]:
                    o.select_set(True)
            bpy.ops.object.duplicate_move_linked()

        else:
            # bpy.ops.mesh.primitive_cube_add(location=pos)
            try:
                bpy.ops.import_scene.omsi_model_cfg(filepath=path, import_x=import_x)
            except:
                log("Exception encountered loading: " + path)

            loaded_objs[path] = [o for o in bpy.context.selected_objects]

        if len(bpy.context.selected_objects) > 0:
            if "[surface]" in bpy.context.selected_objects[0].data \
                    and not bpy.context.selected_objects[0].data["[surface]"]:
                pos[2] += get_interpolated_height(terr_heights, pos[0], pos[1])

        for loaded in bpy.context.selected_objects:
            loaded.location = pos
            loaded.rotation_euler = rot[::-1]
            blender_insts.append(loaded)

    return blender_insts
