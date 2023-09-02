# ==============================================================================
#  Copyright (c) 2023 Thomas Mathieson.
# ==============================================================================
import math
import os
import time
from datetime import date

import bmesh
import bpy

from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       IntProperty,
                       FloatProperty
                       )

import mathutils
from . import io_omsi_spline, o3d_node_shader_utils
from .o3d_cfg_parser import read_generic_cfg_file


def log(*args):
    print("[OMSI_Spline_Import]", *args)


class OMSIMapProps(bpy.types.PropertyGroup):
    bl_idname = "propgroup.OMSIMapProps"
    map_path = bpy.props.StringProperty(name="", subtype="FILE_PATH")
    centre_x = bpy.props.IntProperty(name="Centre Tile X", default=0)
    centre_y = bpy.props.IntProperty(name="Centre Tile Y", default=0)
    load_radius = bpy.props.IntProperty(name="Load Radius", default=999999, min=1)
    import_scos = BoolProperty(name="Import SCOs", default=True)
    import_x = BoolProperty(
        name="Import .x Files",
        description="Attempt to import .x files, this can be buggy and only works if you have the correct .x importer "
                    "already installed.",
        default=True,
    )
    import_splines = BoolProperty(
        name="Import Splines",
        description="Import the map's splines",
        default=False
    )
    spline_tess_dist = FloatProperty(
        name="Spline Tesselation Precision",
        description="The minimum distance between spline segments",
        min=0.1,
        max=1000.0,
        default=6.0,
    )
    spline_curve_sag = FloatProperty(
        name="Spline Tesselation Curve Precision",
        description="The minimum sag distance between the curve and the tessellated segment. Note that this is used in "
                    "combination with the above setting, whichever is lower is used by the tessellator.",
        min=0.0005,
        max=1.0,
        default=0.005,
    )
    spline_preview_quality = FloatProperty(
        name="Spline Preview Quality",
        min=0.01,
        max=10.0,
        default=0.2,
    )


class GenerateMapPreviewOp(bpy.types.Operator):
    """Imports an OMSI global.cfg file and generates a preview of it"""
    bl_idname = "import_scene.omsi_map_preview"
    bl_label = "Import OMSI global.cfg"
    bl_options = {'PRESET', 'UNDO'}

    filepath = StringProperty(
        name="File Path"
    )

    import_scos = BoolProperty(
        name="Import SCOs",
        description="Import the SCO files",
        default=False
    )

    import_splines = BoolProperty(
        name="Import Splines",
        description="Import the map's splines",
        default=False
    )

    roadmap_mode = BoolProperty(
        name="Roadmap Mode",
        description="Imports trees, water and full quality splines for roadmap rendering",
        default=False
    )

    spline_preview_quality = FloatProperty(
        name="Spline Preview Quality",
        min=0.01,
        max=20
    )

    clear = BoolProperty(
        name="Clear Preview",
        default=False
    )

    centre_x = IntProperty(
        name="Centre Tile X",
        description="When loading a global.cfg file, the x coordinate of the first tile to load.",
        default=0
    )
    centre_y = IntProperty(
        name="Centre Tile Y",
        description="When loading a global.cfg file, the y coordinate of the first tile to load.",
        default=0
    )
    load_radius = IntProperty(
        name="Load Radius",
        description="When loading a global.cfg file, how many tiles around the centre tile to load. Set to 0 to only "
                    "load the centre tile, 1 loads the centre tile and it's 4 neighbours, 2 loads the centre tile and "
                    "it's 8 neighbours...",
        default=9999,
        min=0
    )

    @staticmethod
    def generate_terrain_mesh(map_path, parent_collection):
        new_mesh = bpy.data.meshes.new("terrain_mesh-" + os.path.basename(map_path))
        verts = [
            [0, 0, 0],
            [300, 0, 0],
            [0, 300, 0],
            [300, 300, 0],
        ]
        faces = [
            [0, 1, 3],
            [0, 3, 2]
        ]
        new_mesh.from_pydata(verts, [], faces)
        if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
            new_mesh.uv_textures.new("UV Map")
        else:
            new_mesh.uv_layers.new(name="UV Map")
        new_mesh.update(calc_edges=True)

        o = bpy.data.objects.new("terrain-" + os.path.basename(map_path), new_mesh)

        if bpy.app.version < (2, 80):
            bpy.context.scene.objects.link(o)
            parent_collection.objects.link(o)

            o.select = True
        else:
            parent_collection.objects.link(o)
            o.select_set(True)

        return o

    def import_tile(self, collection, map_path, import_scos, global_cfg, import_splines, spline_tess_dist,
                    roadmap_mode):
        map_file = read_generic_cfg_file(map_path)

        objs = [self.generate_terrain_mesh(map_path, collection)]
        objs[0].color = (.25, 0.65, 0.15, 1.)
        objs[0].data.materials.append(o3d_node_shader_utils.generate_solid_material((.15, 0.5, 0.15, 1.)))

        if import_splines:
            objs.extend(io_omsi_spline.import_map_preview_splines(map_path, map_file, spline_tess_dist, collection,
                                                                  roadmap_mode))

        return objs

    def create_cameras(self, tile_coords, collection):
        cams = []
        for tile_coord in tile_coords:
            camera = bpy.data.cameras.new("map_cam-{0}".format(tile_coord))
            camera_obj = bpy.data.objects.new("map_cam-{0}".format(tile_coord), camera)
            camera.type = "ORTHO"
            camera.ortho_scale = 300
            camera.clip_start = 1
            camera.clip_end = 10000
            camera_obj.location = mathutils.Vector((tile_coord[0] * 300+150, tile_coord[1] * 300+150, 500))
            if bpy.app.version < (2, 80):
                bpy.context.scene.objects.link(camera_obj)
                if collection is not None:
                    collection.objects.link(camera_obj)
            else:
                collection.objects.link(camera_obj)

            cams.append(camera_obj)

            rv = bpy.context.scene.render.views.new("map_cam-{0}".format(tile_coord))
            rv.camera_suffix = "{0}".format(tile_coord)

        return cams

    def execute(self, context):
        context.window.cursor_set('WAIT')
        if self.clear:
            if bpy.app.version < (2, 80):
                if "Blender-O3D-IO-Map-Preview" not in bpy.data.groups:
                    context.window.cursor_set('DEFAULT')
                    return {"FINISHED"}

                col = bpy.data.groups["Blender-O3D-IO-Map-Preview"]
                bpy.context.window_manager.progress_begin(0, len(col.objects))
                i = 0
                for obj in col.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                    bpy.context.window_manager.progress_update(i)
                    i += 1
                bpy.data.groups.remove(col)
            else:
                if "Blender-O3D-IO-Map-Preview" not in bpy.data.collections:
                    context.window.cursor_set('DEFAULT')
                    return {"FINISHED"}

                col = bpy.data.collections["Blender-O3D-IO-Map-Preview"]
                bpy.context.window_manager.progress_begin(0, len(col.objects))
                i = 0
                for obj in col.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                    bpy.context.window_manager.progress_update(i)
                    i += 1
                bpy.data.collections.remove(col)

            context.window.cursor_set('DEFAULT')
            return {"FINISHED"}

        start_time = time.time()

        if bpy.app.version < (2, 80):
            collection = bpy.data.groups.new("Blender-O3D-IO-Map-Preview")
        else:
            collection = bpy.data.collections.new("Blender-O3D-IO-Map-Preview")
            bpy.context.scene.collection.children.link(collection)

        global_cfg = read_generic_cfg_file(os.path.join(os.path.dirname(self.filepath), "global.cfg"))

        bpy.context.window_manager.progress_begin(0, len(global_cfg["[map]"]))
        i = 0

        working_dir = os.path.dirname(self.filepath)
        objs = []
        map_coords = []
        for map_file in global_cfg["[map]"]:
            x = int(map_file[0])
            y = int(map_file[1])
            path = map_file[2]
            map_coords.append((x, y))

            diff = (self.centre_x - x, self.centre_y - y)
            dist = math.sqrt(diff[0]*diff[0] + diff[1] * diff[1])
            if dist > self.load_radius*0.5+0.5:
                continue

            tile_objs = self.import_tile(collection, os.path.join(working_dir, path), self.import_scos, global_cfg,
                                         self.import_splines, 1/self.spline_preview_quality, self.roadmap_mode)

            # bpy.ops.object.select_all(action='DESELECT')
            # if bpy.app.version < (2, 80):
            #     for o in tile_objs:
            #         if o.parent is None:
            #             o.select = True
            # else:
            #     for o in tile_objs:
            #         if o.parent is None:
            #             o.select_set(True)

            bpy.ops.transform.translate(value=(x * 300, y * 300, 0))

            objs.extend(bpy.context.selected_objects)
            bpy.ops.object.select_all(action='DESELECT')
            log("Loaded preview tile {0}_{1}!".format(x, y))
            bpy.context.window_manager.progress_update(i)
            i += 1

        log("Loaded preview tiles in {0:.3f} seconds".format(time.time() - start_time))

        if self.roadmap_mode:
            self.create_cameras(map_coords, collection)

        if len(global_cfg["[entrypoints]"]) > 0:
            entrypoints_cfg = global_cfg["[entrypoints]"][0]
            entrypoints_cfg = iter(entrypoints_cfg)
            n_entrypoints = int(next(entrypoints_cfg))
            entrypoint_names = set()
            for i in range(n_entrypoints):
                entrypoint = {
                    "ob_index": int(next(entrypoints_cfg)),
                    "obj_id": int(next(entrypoints_cfg)),
                    "inst_index": int(next(entrypoints_cfg)),
                    "pos_x": float(next(entrypoints_cfg)),
                    "pos_y": float(next(entrypoints_cfg)),
                    "pos_z": float(next(entrypoints_cfg)),
                    "rot_x": float(next(entrypoints_cfg)),
                    "rot_y": float(next(entrypoints_cfg)),
                    "rot_z": float(next(entrypoints_cfg)),
                    "rot_w": float(next(entrypoints_cfg)),
                    "map_tile": int(next(entrypoints_cfg)),
                    "name": next(entrypoints_cfg).strip(),
                }

                if entrypoint["name"] in entrypoint_names:
                    continue
                entrypoint_names.update(entrypoint["name"])

                entrypoint_name = "::entrypoint_{0}".format(entrypoint["name"])
                entry_obj = bpy.data.objects.new(entrypoint_name, None)
                if bpy.app.version < (2, 80):
                    bpy.context.scene.objects.link(entry_obj)
                    if collection is not None:
                        collection.objects.link(entry_obj)

                    entry_obj.empty_draw_type = "SINGLE_ARROW"
                    entry_obj.empty_draw_size = 200 if self.roadmap_mode else 500
                else:
                    collection.objects.link(entry_obj)

                    entry_obj.empty_display_type = "SINGLE_ARROW"
                    entry_obj.empty_display_size = 200 if self.roadmap_mode else 500

                location = mathutils.Vector((entrypoint['pos_x'], entrypoint['pos_z'], 0 if self.roadmap_mode else entrypoint['pos_y']))
                map_coord = map_coords[entrypoint['map_tile']]
                location += mathutils.Vector((map_coord[0] * 300, map_coord[1] * 300, 0))
                entry_obj.location = location
                entry_obj.rotation_quaternion = mathutils.Quaternion((entrypoint['rot_x'], entrypoint['rot_y'],
                                                                      entrypoint['rot_z'], entrypoint['rot_w']))

                if self.roadmap_mode:
                    dot_mesh = bpy.data.meshes.new(entrypoint_name + "_dot")
                    dot_obj = bpy.data.objects.new(entrypoint_name + "_dot", dot_mesh)
                    bm = bmesh.new()
                    bm.from_mesh(dot_mesh)
                    if bpy.app.version < (2, 80):
                        geom = bmesh.ops.create_circle(bm,
                                                       cap_ends=True,
                                                       segments=16,
                                                       diameter=8)
                    else:
                        geom = bmesh.ops.create_circle(bm,
                                                       cap_ends=True,
                                                       segments=16,
                                                       radius=4)
                    bm.to_mesh(dot_mesh)
                    dot_obj.location = location+mathutils.Vector((0, 0, 2))

                    dot_mesh.materials.append(
                        o3d_node_shader_utils.generate_solid_material((0, 0, 0, 1)))
                    if bpy.app.version < (2, 80):
                        bpy.context.scene.objects.link(dot_obj)
                        if collection is not None:
                            collection.objects.link(dot_obj)
                    else:
                        collection.objects.link(dot_obj)

                entry_text = bpy.data.curves.new(type="FONT", name=entrypoint_name + "_text")
                entry_text.body = entrypoint["name"]
                if self.roadmap_mode:
                    entry_text.size = 20
                    entry_text.extrude = 0
                    if os.name == "nt":
                        entry_text.font = bpy.data.fonts.load(filepath="C:/Windows/Fonts/GOTHICB.TTF")
                else:
                    entry_text.size = 200
                    entry_text.extrude = 8
                entry_text.offset = 0
                entry_text.space_character = 0.92
                entry_text_obj = bpy.data.objects.new(entrypoint_name + "_text", entry_text)
                entry_text_obj.color = (0.01, 0.02, 0.6, 1.)
                entry_text_obj.data.materials.append(
                    o3d_node_shader_utils.generate_solid_material((0.0025, 0.005, 0.3, 1.)))
                if bpy.app.version < (2, 80):
                    bpy.context.scene.objects.link(entry_text_obj)
                    collection.objects.link(entry_text_obj)
                else:
                    collection.objects.link(entry_text_obj)
                entry_text_obj.location = location + mathutils.Vector((0, 0, 2.5 if self.roadmap_mode else 500))
                if not self.roadmap_mode:
                    entry_text_obj.rotation_euler = (math.radians(90), 0, 0)

                objs.append(entry_obj)
                objs.append((entry_text_obj))

        if self.roadmap_mode:
            bpy.context.scene.render.resolution_x = 1024
            bpy.context.scene.render.resolution_y = 1024

        context.window.cursor_set('DEFAULT')
        return {"FINISHED"}


class ImportMapCFGPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_Omsi_Map'
    bl_label = 'Import Omsi Map'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        self.layout.label(
            text="Tile coords x: " + (str(int(bpy.context.active_object.location[0]//300))
                                      if bpy.context.active_object else "N/A") +
                 " y: " + (str(int(bpy.context.active_object.location[1]//300))
                           if bpy.context.active_object else "N/A"))

        self.layout.separator()
        col_props = self.layout.column(align=True)

        layout_row = col_props.row(align=True)
        layout_row.label(text="Map Path:")
        layout_row.prop(context.scene.omsi_map_data, "map_path")

        col_props.separator()

        col_props.prop(context.scene.omsi_map_data, "centre_x")
        col_props.prop(context.scene.omsi_map_data, "centre_y")
        col_props.prop(context.scene.omsi_map_data, "load_radius")
        col_props.prop(context.scene.omsi_map_data, "import_scos")
        col_props.prop(context.scene.omsi_map_data, "import_x")
        col_props.prop(context.scene.omsi_map_data, "import_splines")
        col_props.prop(context.scene.omsi_map_data, "spline_tess_dist")
        col_props.prop(context.scene.omsi_map_data, "spline_curve_sag")
        col_props.prop(context.scene.omsi_map_data, "spline_preview_quality")

        col_props.separator()
        layout_row = col_props.row(align=True)
        op = layout_row.operator(GenerateMapPreviewOp.bl_idname, text="Preview map", icon="PLUS")
        op.filepath = context.scene.omsi_map_data.map_path
        op.centre_x = context.scene.omsi_map_data.centre_x
        op.centre_y = context.scene.omsi_map_data.centre_y
        op.load_radius = context.scene.omsi_map_data.load_radius
        op.import_scos = context.scene.omsi_map_data.import_scos
        op.import_splines = context.scene.omsi_map_data.import_splines
        op.spline_preview_quality = context.scene.omsi_map_data.spline_preview_quality
        op.clear = False
        op = layout_row.operator(GenerateMapPreviewOp.bl_idname, text="Clear map preview", icon="CANCEL")
        op.clear = True

        op = col_props.operator(GenerateMapPreviewOp.bl_idname, text="Load for roadmap", icon="WORLD")
        op.roadmap_mode = True
        op.filepath = context.scene.omsi_map_data.map_path
        op.centre_x = context.scene.omsi_map_data.centre_x
        op.centre_y = context.scene.omsi_map_data.centre_y
        op.load_radius = context.scene.omsi_map_data.load_radius
        op.import_scos = context.scene.omsi_map_data.import_scos
        op.import_splines = context.scene.omsi_map_data.import_splines
        op.spline_preview_quality = context.scene.omsi_map_data.spline_preview_quality
        op.clear = False

        self.layout.separator()
        col = self.layout.row(align=True)
        op = col.operator("import_scene.omsi_tile", text="Load tiles", icon="PLUS")
        op.filepath = context.scene.omsi_map_data.map_path
        op.centre_x = context.scene.omsi_map_data.centre_x
        op.centre_y = context.scene.omsi_map_data.centre_y
        op.load_radius = context.scene.omsi_map_data.load_radius
        op.import_scos = context.scene.omsi_map_data.import_scos
        op.import_x = context.scene.omsi_map_data.import_x
        op.import_splines = context.scene.omsi_map_data.import_splines
        op.spline_tess_dist = context.scene.omsi_map_data.spline_tess_dist
        op.spline_curve_sag = context.scene.omsi_map_data.spline_curve_sag

        self.layout.separator()
        self.layout.label(text="© Thomas Mathieson " + date.today().year.__str__())


classes = [
    OMSIMapProps,
    ImportMapCFGPanel,
    GenerateMapPreviewOp
]


def get_classes():
    return classes[:]


def register():
    # Classes are registered and unregistered by __init__.py
    bpy.types.Scene.omsi_map_data = bpy.props.PointerProperty(type=OMSIMapProps)


def unregister():
    del bpy.types.Scene.omsi_map_data
