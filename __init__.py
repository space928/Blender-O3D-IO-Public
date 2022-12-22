# ==============================================================================
#  Copyright (c) 2022 Thomas Mathieson.
# ==============================================================================

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
# <pep8 compliant>

bl_info = {
    "name": "Import OMSI model.cfg files",
    "author": "Adam/Thomas Mathieson",
    "version": (0, 1, 3),
    "blender": (3, 1, 0),
    "location": "File > Import-Export",
    "description": "Import OMSI model.cfg files, their mesh's, UV's, and materials",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}

from .o3d_io import io_o3d_import, io_o3d_export
import bpy
from mathutils import Matrix

from bpy_extras.io_utils import (
    ImportHelper,
    ExportHelper,
    axis_conversion,
)

if not (bpy.app.version[0] < 3 and bpy.app.version[1] < 80):
    pass

from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       CollectionProperty
                       )


def log(*args):
    print("[O3D_IO]", *args)


# https://blender.stackexchange.com/a/243063
def run_ops_without_view_layer_update(func, *args):
    from bpy.ops import _BPyOpsSubModOp

    view_layer_update = _BPyOpsSubModOp._view_layer_update

    def dummy_view_layer_update(context):
        pass

    try:
        _BPyOpsSubModOp._view_layer_update = dummy_view_layer_update

        ret = func(*args)

    finally:
        _BPyOpsSubModOp._view_layer_update = view_layer_update

    return ret


def make_annotations(cls):
    """
    Converts class fields to annotations if running with Blender 2.8

    Credit to: https://github.com/CGCookie/blender-addon-updater/pull/49
    :param cls: class to convert
    :return: converted class
    """
    if bpy.app.version < (2, 80):
        return cls
    if bpy.app.version >= (2, 93, 0):
        bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, bpy.props._PropertyDeferred)}
    else:
        bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
    # bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls


class ImportModelCFG(bpy.types.Operator, ImportHelper):
    """Imports an OMSI model file from a CFG, SCO, or O3D file"""
    bl_idname = "import_scene.omsi_model_cfg"
    bl_label = "Import OMSI Model.cfg"
    bl_options = {'PRESET', 'UNDO'}

    # ImportHelper mixin class uses this
    filename_ext = ".o3d"

    filter_glob = StringProperty(
        default="*.cfg;*.sco;*.o3d",
        options={'HIDDEN'},
    )

    # Selected files
    files = CollectionProperty(type=bpy.types.PropertyGroup)

    def execute(self, context):
        """
        Imports the selected CFG/SCO/O3D file
        :param context: blender context
        :return: success message
        """
        context.window.cursor_set('WAIT')
        run_ops_without_view_layer_update(io_o3d_import.do_import, self.filepath, context)
        context.window.cursor_set('DEFAULT')

        return {'FINISHED'}


#if not (bpy.app.version[0] < 3 and bpy.app.version[1] < 80):
#    @orientation_helper(axis_forward='Y', axis_up='Z')
class ExportModelCFG(bpy.types.Operator, ExportHelper):
    """Imports an OMSI model file from a CFG, SCO, or O3D file"""
    bl_idname = "export_scene.omsi_model_cfg"
    bl_label = "Export OMSI Model.cfg"

    filename_ext = ".o3d"
    check_extension = None

    filter_glob = StringProperty(
        default="*.cfg;*.sco;*.o3d",
        options={'HIDDEN'},
    )
    use_selection = BoolProperty(
        name="Selection Only",
        description="Export selected objects only",
        default=False,
    )
    global_scale = FloatProperty(
        name="Scale",
        min=0.01,
        max=1000.0,
        default=1.0,
    )

    def execute(self, context):
        context.window.cursor_set('WAIT')

        global_matrix = axis_conversion(
            from_forward='Y',
            from_up='Z',
            to_forward='Z',
            to_up='Y',
        ).to_4x4() @ Matrix.Scale(self.global_scale, 4)

        io_o3d_export.do_export(self.filepath, context, global_matrix, self.use_selection)

        context.window.cursor_set('DEFAULT')

        return {'FINISHED'}

    #def draw(self, context):
    #    layout = self.layout
    #    layout.use_property_split = True
    #    layout.use_property_decorate = False
    #    sfile = context.space_data
    #    operator = sfile.active_operator
    #    # col = layout.column(heading="Format")
    #    # col.prop(operator, "use_ascii")


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportModelCFG.bl_idname, text="OMSI Model Config (*.cfg, *.sco, *.o3d)")


def menu_func_export(self, context):
    self.layout.operator(ExportModelCFG.bl_idname, text="OMSI Model Config (*.cfg, *.sco, *.o3d)")


classes = [
    ImportModelCFG,
    ExportModelCFG
]


def register():
    for cls in classes:
        cls = make_annotations(cls)
        bpy.utils.register_class(cls)

    # Compat with 2.7x and 3.x
    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
        bpy.types.INFO_MT_file_import.append(menu_func_import)
        bpy.types.INFO_MT_file_export.append(menu_func_export)
    else:
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    # Compat with 2.7x and 3.x
    if bpy.app.version[0] < 3 and bpy.app.version[1] < 80:
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
        bpy.types.INFO_MT_file_export.remove(menu_func_export)
    else:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    # importer = ImportModelCFG(None)
    # importer.filepath = "D:/Program Files/OMSI 2/Vehicles/GPM_C2/Model/passengercabin_C2_V3.cfg"
    # importer.execute(None)
    # bpy.ops.import_scene.omsi_model_cfg(filepath="D:/Program Files/OMSI 2/Vehicles/GPM_C2/Model/passengercabin_C2_V3.cfg")
