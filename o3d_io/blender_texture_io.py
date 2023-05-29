# ==============================================================================
#  Copyright (c) 2022 Thomas Mathieson.
# ==============================================================================

import os
import bpy
import numpy as np
from .dds_loader.dds_loader import DDSTexture, FormatNotValid, FormatNotSupported


def log(*args):
    print("[O3D_Texture_Import]", *args)


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


def load_image(base_file_path, texture_path, abs_path=False):
    if base_file_path[-3:] == "sco":
        tex_file = os.path.join(os.path.dirname(base_file_path), "texture", texture_path.lower())
    elif base_file_path[-3:] == "map":
        tex_file = os.path.join(os.path.dirname(base_file_path), "..", "..", texture_path.lower())
    else:
        tex_file = os.path.join(os.path.dirname(base_file_path), "..", "texture", texture_path.lower())

    if abs_path:
        tex_file = texture_path.lower()

    pre, ext = os.path.splitext(tex_file)
    is_dds = False
    if os.path.isfile(pre + ".dds"):
        tex_file = pre + ".dds"
        is_dds = True

    # Attempt a manual search for the file if we couldn't find it
    if not os.path.isfile(tex_file):
        tex_dir = os.path.dirname(base_file_path)
        while True:
            tex_file = os.path.join(tex_dir, texture_path.lower())
            if os.path.isfile(tex_file):
                break
            tex_file = os.path.join(tex_dir, "texture", texture_path.lower())
            if os.path.isfile(tex_file):
                break

            last_dir = tex_dir
            tex_dir = os.path.dirname(tex_dir)
            # Exit case if no texture was found
            if os.path.ismount(tex_dir) or last_dir == tex_dir:
                break

    if os.path.isfile(tex_file):
        # TODO: Alpha_8_UNORM DDS files are not supported by Blender
        image = bpy.data.images.load(tex_file,
                                     check_existing=True)

        if not image.has_data and is_dds:
            # image.has_data doesn't necessarily mean Blender can't load it (sometimes it's deferred), but there's a
            # good chance it failed.
            # Try loading the DDS file ourselves
            dds = DDSTexture()
            try:
                dds.load(tex_file)
            except FormatNotValid as e:
                log("DDS format not valid: " + str(e))
                dds = None
            except FormatNotSupported as e:
                log("DDS format not supported: " + str(e))
                dds = None

            if dds and dds.dxgi_format == 65:
                # log("Loading Alpha_8 DDS file...")
                # For now, we only support ALPHA_8_UNORM DDS files as they are uncompressed, and so far have been the
                # only dds format encountered which isn't supported by Blender
                surf = dds.surfaces[0]

                image = bpy.data.images.new(tex_file, surf.width, surf.height, alpha=dds.header.ddspf.dwABitMask != 0)

                # Fast way to set pixels (since 2.83)
                image.pixels.foreach_set(np.repeat(np.array(surf.data, np.dtype('B')).astype(np.float32), 4))

                # Pack the image into .blend so it gets saved with it
                image.pack()

        return image
    else:
        log("WARNING: Couldn't find texture: {0}".format(texture_path))
        return None


def load_texture_into_new_slot(base_file_path, texture_path, mat, abs_path=False):
    image = load_image(base_file_path, texture_path, abs_path)

    if image is not None:
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
