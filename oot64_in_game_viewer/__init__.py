bl_info = {
    'name': 'OoT64 Live In-Game Inject/Viewer',
    'author': 'Dragorn421',
    'version': (1, 0, 0),
    'blender': (2, 79, 0),
    'location': '?',
    'description': 'Load and view an object in-game, live',
    'warning': '',
    'wiki_url': '?',
    'support': 'COMMUNITY',
    'category': 'Import-Export'
}


import bpy
import bpy_extras

import os
import subprocess
import re
import time

# reload files
import importlib
loc = locals()
for n in (
    'communicate', 'export_objex_mtl', 'export_objex_anim',
    'properties', 'interface', 'const_data', 'util', 'logging_util',
    'rigging_helpers', 'data_updater', 'view3d_copybuffer_patch',
    'addon_updater', 'addon_updater_ops',
):
    if n in loc:
        importlib.reload(loc[n])
del importlib

from . import communicate

def zzconvert_path_update(self, context):
    if not self.zzconvert_path:
        return
    print(self.zzconvert_path)
    if bpy.data.filepath:
        abs_path = bpy_extras.io_utils.path_reference(self.zzconvert_path, os.path.dirname(bpy.data.filepath), '.', mode='ABSOLUTE')
        print(abs_path)
        if abs_path != self.zzconvert_path:
            self.zzconvert_path = abs_path # recursive call
            return
    stdout = None
    stderr = None
    try:
        p = subprocess.run(self.zzconvert_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout = p.stdout
        stderr = p.stderr
        print('stdout', stdout)
        print('stderr', stderr)
    except FileNotFoundError as e:
        print('FileNotFoundError with zzconvert_path =', self.zzconvert_path)
    if stdout is not None:
        self.zzconvert_version = ('OLD' if b'|   Ben   | @                 - Uncle Ben' in stdout else 'NEW')

class OOT64_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    temp_files_basename = bpy.props.StringProperty(
        subtype='FILE_PATH',
        name='Temporary files base name',
        default='//temp_liveinject_data'
    )
    zzconvert_path = bpy.props.StringProperty(
        subtype='FILE_PATH',
        name='zzconvert location',
        default='',
        update=zzconvert_path_update
    )
    zzconvert_version = bpy.props.EnumProperty(
        items=[
            ('OLD', 'r7-','r7 and earlier',1),
            ('NEW', 'r8+','r8 and later',2),
        ],
        name='zzconvert version',
        default='OLD'
    )
    export_as = bpy.props.EnumProperty(
        items=[
            # parameters according to export_scene_so.obj
            # export_scene.obj(use_triangles=True, use_vertex_groups=False, use_blen_objects=True, group_by_object=False,
            ('obj', 'Obj (vanilla Blender)','Wavefront',1),
            ('obj_so', 'Obj (SO)','Wavefront SharpOcarina',2),   # export_scene_so.obj
            ('objex_old', 'Objex (old)','Extended OBJ (old)',3), # export_scene.objex
            ('objex2', 'Objex2','Extended OBJ (objex2, new)',4), # objex.export
        ],
        name='Export as',
        default='obj'
    )

    actor_type = bpy.props.IntProperty(
        name='Actor type',
        description='Type of the in-game actor involved in the loading process',
        default=1
    )
    actor_id = bpy.props.IntProperty(
        name='Actor id',
        description='ID of the in-game actor involved in the loading process',
        default=5
    )
    actor_context_address = bpy.props.IntProperty(
        name='Actor context address',
        description='Address of the actor context MINUS 0x80000000, usually global + 0x01C24, default value is for mq debug',
        default=(0x80212020 + 0x01C24 - 0x80000000)
    )

    def draw(self, context):
        self.layout.prop(self, 'temp_files_basename')
        self.layout.prop(self, 'zzconvert_path')
        self.layout.prop(self, 'zzconvert_version')
        self.layout.prop(self, 'export_as')
        self.layout.prop(self, 'actor_type')
        self.layout.prop(self, 'actor_id')
        self.layout.prop(self, 'actor_context_address')

class OOT64_OT_export_live_inject(bpy.types.Operator):
    bl_idname = 'oot64.export_live_inject'
    bl_label = 'Export the current blend and load it live.'

    def execute(self, context):
        execute_start = time.time()
        """
        root = 'D:\\OoT64\\'
        bpy.ops.objex.export(filepath=root + 'custom actors\\zzrtl\\in_game_viewer\\exp\\data.objex')
        export_done = time.time()
        obj_h = subprocess.check_output(
                [root + 'zzconvert_rewrite\\zzconvert-8b-038-cli.exe',
                    '--out', root + 'custom actors\\zzrtl\\in_game_viewer\\exp\\data.zobj',
                    '--in', root + 'custom actors\\zzrtl\\in_game_viewer\\exp\\data.objex',
                    '--scale', '1000'])
        obj_h = obj_h.decode()
        zzconvert_done = time.time()
        """
        addon_preferences = context.user_preferences.addons[__package__].preferences
        if not addon_preferences.zzconvert_path:
            self.report({'WARNING'}, 'Path to zzconvert is not set, check the addon preferences')
            return {'CANCELLED'}

        export_filepath = '%s_%s' % (addon_preferences.temp_files_basename, addon_preferences.export_as)
        print('export_filepath =', export_filepath)
        # 421fixme what if .blend isnt saved
        # I think it will just use the working directory
        export_filepath = bpy_extras.io_utils.path_reference(export_filepath, os.path.dirname(bpy.data.filepath), '.', mode='ABSOLUTE')
        print('export_filepath =', export_filepath)
        print('export_as =', addon_preferences.export_as)
        if addon_preferences.export_as == 'obj':
            bpy.ops.export_scene.obj(filepath=export_filepath,
                use_triangles=True, use_vertex_groups=False, use_blen_objects=True, group_by_object=False)
        elif addon_preferences.export_as == 'obj_so':
            bpy.ops.export_scene_so.obj(filepath=export_filepath)
        elif addon_preferences.export_as == 'objex_old':
            armatureObject = None
            for obj in bpy.context.scene.objects:
                if obj.type == 'ARMATURE':
                    armatureObject = obj
                obj.select = False
            if armatureObject:
                bpy.context.scene.objects.active = armatureObject
                armatureObject.select = True
            bpy.ops.export_scene.objex(filepath=export_filepath)
        elif addon_preferences.export_as == 'objex2':
            bpy.ops.objex.export(filepath=export_filepath)
        else:
            self.report({'WARNING'}, 'Unknown export_as = %r' % addon_preferences.export_as)
            return {'CANCELLED'}
        export_done = time.time()

        zobj_path = '%s_%s.zobj' % (export_filepath, addon_preferences.zzconvert_version)
        print('zobj_path =', zobj_path)
        # execute
        print('zzconvert_version =', addon_preferences.zzconvert_version)
        if addon_preferences.zzconvert_version == 'NEW':
            p = subprocess.run(
                [addon_preferences.zzconvert_path,
                    '--out', zobj_path,
                    '--in', export_filepath,
                    '--scale', '1000'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        else: # OLD
            p = subprocess.run(
                [addon_preferences.zzconvert_path,
                    'object', export_filepath, zobj_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        # check errors
        if p.returncode != 0:
            self.report({'WARNING'}, 'zzconvert failed to convert to zobj, open the console for details')
            print('zzconvert failed to convert to zobj')
            print('returncode =', p.returncode)
            print('stdout:')
            print(p.stdout.decode())
            print('stderr:')
            print(p.stderr.decode())
            return {'CANCELLED'}
        # obj_h
        if addon_preferences.zzconvert_version == 'NEW':
            obj_h = p.stdout.decode()
        else: # OLD
            stdout = p.stdout

            i = 0
            expectedStart = [
                "     _____",
                "   /`     `\\",
                "  :   RIP   :        With great power comes",
                "  |         |          great responsibility.",
                "  |  Uncle  |", # random line
                "  |   Ben   | @                 - Uncle Ben",
                "__|.........|_)________________________________",
                "   .........                 .",
                "   .........                \\//",
                "",
                "[-] zzconvert v",#0.01 r7 by Dr.Disco <z64.me>",
                "[-] Built:",# Jul  6 2019 13:50:48",
                "[*] A very big thanks to Ideka for all the early hardware testing, and",
                "[*] CDi-Fails and CrookedPoe for such thorough testing and debugging",
                "[*] help throughout this long, grueling development process!"
            ]

            obj_h_lines = []
            for l in stdout.decode().split('\n'):
                skipLine = False
                # Using startswith handles the i == 4 case and \r\n
                if i < len(expectedStart) and l.startswith(expectedStart[i]):
                    pass
                else:
                    obj_h_lines.append(l)
                i += 1
            obj_h = '\n'.join(obj_h_lines)
        zzconvert_done = time.time()

        models = dict()
        skeletons = dict()
        animations = dict()

        for l in obj_h.split('\n'):
            print('l =', l)
            m = re.match(r'^ *#define +([a-zA-Z0-9_]+) +0x([0-9a-fA-F]+)\r?$', l)
            if not m:
                print('not a #define, ignore')
                continue
            print(m.group(1), m.group(2))
            name = m.group(1)
            offset = int(m.group(2), 16)
            if name.startswith('DL_'):
                models[name] = offset
            elif name.startswith('SKEL_'):
                skeletons[name] = offset
            elif name.startswith('ANIM_'):
                animations[name] = offset
            elif name.startswith('TEX_'):
                pass
            elif name.startswith('PAL_'):
                pass
            else:
                print('What is this?', name)
        parse_zzoutput_done = time.time()

        mf = communicate.MutualFeedback(None, None)
        mf.findActor(addon_preferences.actor_type, addon_preferences.actor_id, addon_preferences.actor_context_address + 0x80000000)
        mf.ping('Connectivity test')
        findActor_done = time.time()
        with open(zobj_path, mode='rb') as f:
            data = f.read()
        zobj_read_done = time.time()

        anyIn = lambda iterable: next(iter(iterable))
        if skeletons:
            skeletonOffsetKey = anyIn(skeletons.keys())
            animationOffsetKey = anyIn(animations.keys())
            self.report({'INFO'}, 'Showing skeleton %s with animation %s' % (skeletonOffsetKey, animationOffsetKey))
            mf.loadObject(data, animations={skeletons[skeletonOffsetKey]: (animations[animationOffsetKey],)})
        else:
            modelOffsetKey = anyIn(models.keys())
            self.report({'INFO'}, 'Showing model %s' % modelOffsetKey)
            mf.loadObject(data, models=(models[modelOffsetKey],))
        loadObject_done = time.time()

        j = 0
        for i in range(100):
            idle = mf.tick()
            if idle and not mf.message_queue:
                j += 1
                if j > 5:
                    break
            else:
                j = 0
            time.sleep(0.05)
        finished = time.time()

        prev = execute_start
        for lbl, t in (
            ('export_done', export_done),
            ('zzconvert_done', zzconvert_done),
            ('parse_zzoutput_done', parse_zzoutput_done),
            ('findActor_done', findActor_done),
            ('zobj_read_done', zobj_read_done),
            ('loadObject_done', loadObject_done),
            ('finished', finished),
        ):
            print(lbl, (t-prev)*1000, 'ms')
            prev = t
        return {'FINISHED'}


classes = (
    OOT64_AddonPreferences,
    OOT64_OT_export_live_inject,
)

def register():
    for clazz in classes:
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
