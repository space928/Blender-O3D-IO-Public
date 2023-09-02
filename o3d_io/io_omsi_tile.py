# ==============================================================================
#  Copyright (c) 2023 Thomas Mathieson.
# ==============================================================================

import math
import os.path
import time

import bpy
import struct

import mathutils
from . import o3d_node_shader_utils, io_omsi_spline, io_o3d_import
from .blender_texture_io import load_texture_into_new_slot
from .o3d_cfg_parser import read_generic_cfg_file


def log(*args):
    print("[OMSI_Tile_Import]", *args)


def do_import(context, filepath, import_scos, import_splines, spline_tess_dist, spline_tess_angle, import_x,
              centre_x, centre_y, load_radius):
    # Read global.cfg
    global_cfg = read_generic_cfg_file(os.path.join(os.path.dirname(filepath), "global.cfg"))

    if filepath[-3:] == "map":
        import_tile(context, filepath, import_scos, global_cfg, import_splines, spline_tess_dist, spline_tess_angle,
                    import_x)
    elif filepath[-3:] == "cfg":
        start_time = time.time()
        working_dir = os.path.dirname(filepath)
        objs = []
        tiles = 0
        loaded_objs_cache = {}
        for map_file in global_cfg["[map]"]:
            x = int(map_file[0])
            y = int(map_file[1])
            path = map_file[2]

            diff = (centre_x - x, centre_y - y)
            dist = math.sqrt(diff[0]*diff[0] + diff[1] * diff[1])
            if dist > load_radius*0.5+0.5:
                continue

            log("### Loading " + path)

            tile_objs = import_tile(context, os.path.join(working_dir, path), import_scos, global_cfg, import_splines,
                                    spline_tess_dist, spline_tess_angle, import_x, loaded_objs_cache)

            bpy.ops.object.select_all(action='DESELECT')
            if bpy.app.version < (2, 80):
                for o in tile_objs:
                    if o.parent is None:
                        o.select = True
            else:
                for o in tile_objs:
                    if o.parent is None:
                        o.select_set(True)

            bpy.ops.transform.translate(value=(x * 300, y * 300, 0))

            objs.extend(bpy.context.selected_objects)
            bpy.ops.object.select_all(action='DESELECT')
            tiles += 1

        log("### Loaded {0} objects across {1} tiles in {2} seconds!".format(len(objs), tiles,
                                                                             time.time() - start_time))


def import_tile(context, filepath, import_scos, global_cfg, import_splines, spline_tess_dist, spline_tess_angle,
                import_x, loaded_objs_cache=None):
    start_time = time.time()

    if bpy.app.version < (2, 80):
        collection = bpy.data.groups.new(os.path.basename(filepath[:-4]))
    else:
        collection = bpy.data.collections.new(os.path.basename(filepath[:-4]))
        bpy.context.scene.collection.children.link(collection)

    map_file = read_generic_cfg_file(filepath)

    # Make terrain mesh
    terrain_obj, terr_heights = import_terrain_mesh(filepath, global_cfg)

    blender_insts = []
    spline_defs = None
    if import_splines:
        splines = io_omsi_spline.import_map_splines(filepath, map_file, spline_tess_dist, spline_tess_angle, collection)
        blender_insts.extend(splines[0])
        spline_defs = splines[1]
    else:
        spline_defs = io_omsi_spline.load_spline_defs(map_file)

    if import_scos:
        blender_insts.extend(import_map_objects(filepath, map_file, terr_heights, import_x, collection,
                                                spline_defs, loaded_objs_cache))

    blender_insts.append(terrain_obj)

    # Make collection
    if bpy.app.version < (2, 80):
        bpy.context.scene.objects.link(terrain_obj)

    collection.objects.link(terrain_obj)

    bpy.ops.object.select_all(action='DESELECT')

    if bpy.app.version < (2, 80):
        terrain_obj.select = True
        bpy.ops.object.shade_smooth()
        for o in blender_insts:
            o.select = True
    else:
        terrain_obj.select_set(True)
        bpy.ops.object.shade_smooth()
        for o in blender_insts:
            o.select_set(True)

    bpy.data.scenes[context.scene.name]["map_data"] = map_file

    log("Loaded tile {0} in {1} seconds!".format(filepath, time.time() - start_time))
    return blender_insts


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

    new_mesh = bpy.data.meshes.new("terrain_mesh-" + os.path.basename(filepath))
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
    return bpy.data.objects.new("terrain-" + os.path.basename(filepath), new_mesh), heights


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


def import_map_objects(filepath, map_file, terr_heights, import_x, parent_collection, spline_defs, loaded_objs=None):
    if loaded_objs is None:
        loaded_objs = {}
    blender_insts = []

    omsi_dir = os.path.abspath(os.path.join(os.path.dirname(filepath), os.pardir, os.pardir))
    # log("Assuming OMSI directory of: ", omsi_dir)

    objs = parse_map_data(map_file, omsi_dir)

    log("Loaded {0} objects!".format(len(objs)))

    for obj in objs:
        pos = mathutils.Vector(obj["pos"])
        path = obj["path"]
        rot = mathutils.Vector([-math.radians(x) for x in obj["rot"]]).zyx
        obj_name = os.path.basename(path)[:-4]

        if "spline" in obj:
            # Weird edge case in OMSI where spline_attachments with a negative spline distance
            if pos.z < 0 or pos.z > spline_defs[obj["spline"]].length:
                continue

        if path in loaded_objs:
            # Save time by duplicating existing objects
            container_obj, new_objs = clone_object(loaded_objs, obj_name, parent_collection, path)
            blender_insts.extend(new_objs)
        else:
            # bpy.ops.mesh.primitive_cube_add(location=pos)
            imported_objs = []
            try:
                imported_objs = io_o3d_import.do_import(path, bpy.context, import_x, "", True, False, parent_collection)
            except:
                log("Exception encountered loading: " + path)

            container_obj = bpy.data.objects.new(obj_name, None)
            parent_collection.objects.link(container_obj)

            loaded_objs[path] = [o for o in imported_objs]
            for o in imported_objs:
                o.parent = container_obj

            imported_objs.append(container_obj)

            blender_insts.extend(imported_objs)

        align_tangent = "tangent_to_spline" in obj
        if obj["tree_data"] is not None:
            # TODO: Handle tree replacement
            container_obj["tree_data"] = obj["tree_data"]
        if "attach" in obj:
            container_obj["attach"] = obj["attach"]

        # TODO: Copy across any [object] specific parameters to the container bl_object

        if "spline" in obj:
            container_obj["cfg_data"] = obj
            container_obj["spline_id"] = spline_defs[obj["spline"]].id
            container_obj["rep_distance"] = obj["rep_distance"]
            container_obj["rep_range"] = obj["rep_range"]
            container_obj["tangent_to_spline"] = obj["tangent_to_spline"]
            if "repeater_x" in obj:
                container_obj["repeater_x"] = obj["repeater_x"]
                container_obj["repeater_y"] = obj["repeater_y"]
            # log(f"Rep {obj['id']} {obj['rep_distance']} {obj['rep_range']}\t:::")
            d = obj["rep_distance"]
            while d < obj["rep_range"] and (d + pos.z < spline_defs[obj["spline"]].length):
                # Clone the object and transform it
                container_obj_rep, new_objs = clone_object(loaded_objs, obj_name, parent_collection, path)
                blender_insts.extend(new_objs)

                pos_s = pos.xzy
                pos_s += mathutils.Vector((0, d, 0))
                pos_rep, spl_rot = spline_defs[obj["spline"]].evaluate_spline(pos_s, True, True)
                if align_tangent:
                    spl_rot.x = -spl_rot.x
                    spl_rot.y = -spl_rot.y
                else:
                    spl_rot.x = 0
                    spl_rot.y = 0

                # log(f"\t\t inst:{pos_s} -> {pos_rep}")
                container_obj_rep.location = pos_rep
                container_obj_rep.rotation_euler = rot + spl_rot
                container_obj_rep["rep_parent"] = obj

                d += obj["rep_distance"]

            # Position is relative to the spline
            pos, spl_rot = spline_defs[obj["spline"]].evaluate_spline(pos.xzy, True, True)
            if align_tangent:
                spl_rot.x = -spl_rot.x
                spl_rot.y = -spl_rot.y
            else:
                spl_rot.x = 0
                spl_rot.y = 0
            rot += spl_rot
        else:
            pos.z += get_interpolated_height(terr_heights, pos.x, pos.y)

        container_obj.location = pos
        container_obj.rotation_euler = rot

    return blender_insts


def clone_object(loaded_objs, obj_name, parent_collection, path):
    blender_insts = []
    if bpy.app.version < (2, 80):
        container_obj = bpy.data.objects.new(obj_name, None)
        parent_collection.objects.link(container_obj)
        blender_insts.append(container_obj)
        for o in loaded_objs[path]:
            cop = o.copy()
            bpy.context.scene.objects.link(cop)
            parent_collection.objects.link(cop)
            cop.parent = container_obj
            blender_insts.append(cop)
    else:
        container_obj = bpy.data.objects.new(obj_name, None)
        parent_collection.objects.link(container_obj)
        blender_insts.append(container_obj)
        for o in loaded_objs[path]:
            cop = o.copy()
            parent_collection.objects.link(cop)
            cop.parent = container_obj
            blender_insts.append(cop)
    return container_obj, blender_insts


def parse_map_data(map_file, omsi_dir):
    objs = []

    if "[object]" in map_file:
        for lines in map_file["[object]"]:
            # I'm not sure what line 0, it's almost always a 0, rarely it's a 1 and only on Berlin is it ever 2
            path = lines[1]
            obj_id = int(lines[2])
            pos = [float(lines[3 + x]) for x in range(3)]
            rot = [float(lines[6 + x]) for x in range(3)]  # ZYX (Z-Up)

            try:
                obj_type = int(lines[9])
            except ValueError:
                obj_type = 0

            tree_data = None
            if obj_type == 4:
                tree_data = {
                    "texture": lines[10],
                    "height": float(lines[11]),
                    "aspect": float(lines[12])
                }
            elif obj_type == 7:
                pass  # Bus stop
            elif obj_type == 1:
                pass  # Label

            objs.append({
                "cfg_type": "object",
                "path": os.path.join(omsi_dir, path),
                "id": obj_id,
                "pos": pos, "rot": rot,
                "tree_data": tree_data
            })

    if "[attachObj]" in map_file:
        for lines in map_file["[attachObj]"]:
            path = lines[1]
            obj_id = int(lines[2])
            pos = [float(lines[4 + x]) for x in range(3)]
            rot = [float(lines[5 + x]) for x in range(3)]  # ZYX (Z-Up)

            try:
                obj_type = int(lines[10])
            except ValueError:
                obj_type = 0

            tree_data = None
            if obj_type == 4:
                tree_data = {
                    "cfg_type": "attachObj",
                    "texture": lines[11],
                    "height": float(lines[12]),
                    "aspect": float(lines[13])
                }
            elif obj_type == 7:
                pass  # Bus stop
            elif obj_type == 1:
                pass  # Label

            objs.append({
                "path": os.path.join(omsi_dir, path),
                "id": obj_id,
                "pos": pos, "rot": rot,
                "tree_data": tree_data,
                "attach": int(lines[3])
            })

    if "[splineAttachement]" in map_file:
        for lines in map_file["[splineAttachement]"]:
            try:
                obj_type = int(lines[13])
            except ValueError:
                obj_type = 0

            tree_data = None
            if obj_type == 4:
                tree_data = {
                    "texture": lines[14],
                    "height": float(lines[15]),
                    "aspect": float(lines[16])
                }
            elif obj_type == 7:
                pass  # Bus stop
            elif obj_type == 1:
                pass  # Label

            objs.append({
                "cfg_type": "splineAttachement",
                "path": os.path.join(omsi_dir, lines[1]),
                "id": int(lines[2]),
                "pos": [float(lines[4 + x]) for x in range(3)],
                "rot": [float(lines[7 + x]) for x in range(3)],
                "tree_data": tree_data,
                "spline": int(lines[3]),
                "rep_distance": float(lines[10]),
                "rep_range": float(lines[11]),
                "tangent_to_spline": int(lines[12]) == 1
            })

    if "[splineAttachement_repeater]" in map_file:
        for lines in map_file["[splineAttachement_repeater]"]:
            try:
                obj_type = int(lines[15])
            except ValueError:
                obj_type = 0

            tree_data = None
            if obj_type == 4:
                tree_data = {
                    "texture": lines[16],
                    "height": float(lines[17]),
                    "aspect": float(lines[18])
                }
            elif obj_type == 7:
                pass  # Bus stop
            elif obj_type == 1:
                pass  # Label

            objs.append({
                "cfg_type": "splineAttachement_repeater",
                "path": os.path.join(omsi_dir, lines[3]),
                "id": int(lines[4]),
                "pos": [float(lines[6 + x]) for x in range(3)],
                "rot": [float(lines[9 + x]) for x in range(3)],
                "tree_data": tree_data,
                "spline": int(lines[5]),
                "rep_distance": float(lines[12]),
                "rep_range": float(lines[13]),
                "tangent_to_spline": int(lines[14]) == 1,
                "repeater_x": int(lines[1]),  # I still don't know what these do
                "repeater_y": int(lines[2]),  # I still don't know what these do
            })

    return objs
