
#include <z64ovl/oot/debug.h>
#include <z64ovl/z64ovl_helpers.h>

#include <string.h>

#define OBJ_ID         5
#define ACT_ID         5

#ifdef __IDE_VS__
// copied from z64ovl/h/mips.h
typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int8_t   s8;
typedef int16_t  s16;
typedef int32_t  s32;
typedef int64_t  s64;
typedef float    f32;
typedef double   f64;
#endif

//#define ADDRESS_OF_OBJECT_SEGMENT (((u32*)RAM_SEGMENT_TABLE) + 6)

typedef enum { TYPE_NONE, TYPE_MODEL, TYPE_RIG } dynamic_object_content_type;

typedef struct dynamic_object_content {
	dynamic_object_content_type type;
	u8 draw;
	union {
		struct {
			u32 dlist;
		} model;
		struct {
			u32 skeleton;
			u32 animationAmount;
			u32* animations;
			// convenient place for storing data
			u8 play;
			z64_skelanime_t anim;
		} rig;
	};
	struct dynamic_object_content* next;
} dynamic_object_content;


#define MSG_IDLE 0
#define MSG_PING 1
#define MSG_PONG 2
// payload: address
// address is MSG_FREE'd once read by plugin
#define MSG_LOG 3

// payload: size
#define MSG_MALLOC 10
// payload: address
#define MSG_MALLOC_RESULT 11
// payload: address
#define MSG_FREE 12

#define MSG_CLEAR_OBJECT 20
// payload: address
#define MSG_SET_OBJECT 21
// payload: offset
#define MSG_ADD_OBJECT_CONTENT_MODEL 22
// payload: anim.skeletonOffset, anim.animOffset
#define MSG_ADD_OBJECT_CONTENT_ANIMATION 23


#define MESSAGE_PAYLOAD_RAW_MAX_LENGTH 4

struct mutual_feedback_io {
	u32 id;
	u32 message_type;
	struct {
		union {
			u32 size;
			void* address;
			u32 offset;
			struct {
				u32 skeletonOffset;
				u32 animOffset;
			} anim;
			struct {
				u32 length;
				u32 data[MESSAGE_PAYLOAD_RAW_MAX_LENGTH];
			} raw;
		};
	} message_payload;
};

typedef struct {
	void* address;
	dynamic_object_content* contents_first; // linked list
} dynamic_object_info;

struct log_entry {
	void* msg;
	struct log_entry* next;
};

typedef struct {

	z64_actor_t actor;
	
	// actor -> plugin
	struct mutual_feedback_io output;

	// plugin -> actor
	struct mutual_feedback_io input;

	dynamic_object_info dynamicObject;

	struct log_entry* log_entries_first; // linked list

} entity_t;

// fixme: z_malloc(_n * 2 + 20
// "##__VA_ARGS__": no idea. https://gcc.gnu.org/onlinedocs/cpp/Variadic-Macros.html
#define LOG(en, msg_arg, ...) {             \
	u32 _n;                                 \
	void* _msg;                             \
	struct log_entry* _entry;               \
	_n = strlen(msg_arg);                   \
	_msg = z_malloc(_n * 2 + 100, "in_game_viewer"); \
	z_sprintf(_msg, msg_arg, ##__VA_ARGS__); \
	_entry = z_malloc(sizeof(struct log_entry), "in_game_viewer"); \
	_entry->msg = _msg;                     \
	_entry->next = en->log_entries_first;   \
	en->log_entries_first = _entry;         \
}

static void init(entity_t* en, z64_global_t* global) {
	// start the mutual feedback loop
	en->output.message_type = MSG_IDLE;
	en->output.id = 1;
	en->input.id = 0;
	// reset dynamic object
	en->dynamicObject.address = 0;
	en->dynamicObject.contents_first = 0;
	//global->common.state_main = 0; // crash the game
	en->log_entries_first = 0;
	//en->actor.pos.x += 100;
	en->actor.pos.y += 10;
	//en->actor.pos.z += 20;
}

void clearObject(dynamic_object_info* obj)
{
	// z_free(en->dynamicObject.address) is left to the plugin side with MSG_FREE
	obj->address = 0;
	dynamic_object_content* next = obj->contents_first;
	obj->contents_first = 0;
	while (next)
	{
		dynamic_object_content* cur = next;
		next = cur->next;
		if (cur->type == TYPE_RIG)
		{
			z_free(cur->rig.animations); // fixme check code when implementing TYPE_RIG
			if (cur->draw && cur->rig.play)
				z_skelanime_free(&cur->rig.anim, (void*) GLOBAL_CONTEXT); // fixme
		}
		z_free(cur);
	}
}

void addObjectContentModel(dynamic_object_info* obj, u32 dlist)
{
	dynamic_object_content** nextOfLast = &obj->contents_first;
	while (*nextOfLast)
		nextOfLast = &(*nextOfLast)->next;
	dynamic_object_content* newContent = z_malloc(sizeof(dynamic_object_content), "in_game_viewer");
	newContent->type = TYPE_MODEL;
	newContent->draw = 1;
	newContent->model.dlist = dlist;
	newContent->next = 0;
	*nextOfLast = newContent;
}

void addObjectContentAnimation(dynamic_object_info* obj, u32 skeleton, u32 anim)
{
	/*
	dynamic_object_content* sameSkeleton;
	dynamic_object_content** nextOfLast = &obj->contents_first;
	while (*nextOfLast)
		if ((*nextOfLast)->rig.skeleton == skeleton)
		{
			sameSkeleton = *nextOfLast;
			break;
		}
	nextOfLast = &(*nextOfLast)->next;
	//*/
	dynamic_object_content** nextOfLast = &obj->contents_first;
	while (*nextOfLast)
	{
		if ((*nextOfLast)->rig.skeleton == skeleton)
			break;
		nextOfLast = &(*nextOfLast)->next;
	}
	if (!(*nextOfLast) || (*nextOfLast)->rig.skeleton != skeleton)
	{
		dynamic_object_content* newContent = z_malloc(sizeof(dynamic_object_content), "in_game_viewer");
		newContent->type = TYPE_RIG;
		newContent->draw = 0;
		newContent->rig.play = 0;
		newContent->rig.skeleton = skeleton;
		newContent->rig.animationAmount = 1;
		newContent->rig.animations = z_malloc(sizeof(u32), "in_game_viewer");
		newContent->rig.animations[0] = anim;
		newContent->next = 0;
		*nextOfLast = newContent;
	}
	// fixme v never tested this!
	/*
	else
	{
		u32 oldAnimationAmount = (*nextOfLast)->rig.animationAmount;
		u32* oldAnimations = (*nextOfLast)->rig.animations;
		u32 newAnimationAmount = oldAnimationAmount + 1;
		u32* newAnimations = z_malloc(sizeof(u32) * newAnimationAmount, "in_game_viewer");
		z_bcopy(oldAnimations, newAnimations, sizeof(u32) * oldAnimationAmount);
		newAnimations[newAnimationAmount - 1] = anim;
		(*nextOfLast)->rig.animationAmount = newAnimationAmount;
		(*nextOfLast)->rig.animations = newAnimations;
	}//*/
}

static void update(entity_t* en, z64_global_t* global) {
	// only the message with higher id is relevant
	if (en->input.id > en->output.id)
	{
		u32 output_message_type = MSG_IDLE;
		// input is more recent, read it, and acknowledge input by answering
		switch (en->input.message_type)
		{
		case MSG_IDLE:
			break;
		case MSG_PING:
			output_message_type = MSG_PONG;
			break;
		case MSG_PONG:
			break;
		case MSG_LOG:
			LOG(en, "test");
			break;
		case MSG_MALLOC:
			output_message_type = MSG_MALLOC_RESULT;
			en->output.message_payload.address = z_malloc(en->input.message_payload.size, "in_game_viewer");
			break;
		case MSG_MALLOC_RESULT:
			LOG(en, "bad MSG_MALLOC_RESULT");
			break;
		case MSG_FREE:
			z_free(en->input.message_payload.address);
			break;
		case MSG_CLEAR_OBJECT:
			clearObject(&en->dynamicObject);
			break;
		case MSG_SET_OBJECT:
			en->dynamicObject.address = en->input.message_payload.address;
			// fixme this prevents from tying everything to a single actor instance
			//global->obj_ctxt.objects[en->actor.alloc_index].data = en->dynamicObject.address;
			break;
		case MSG_ADD_OBJECT_CONTENT_MODEL:
			addObjectContentModel(&en->dynamicObject, en->input.message_payload.offset);
			break;
		case MSG_ADD_OBJECT_CONTENT_ANIMATION:
			addObjectContentAnimation(&en->dynamicObject, en->input.message_payload.anim.skeletonOffset, en->input.message_payload.anim.animOffset);
			break;
		default:
			LOG(en, "unknown code");
			break;
		}
		if (output_message_type == MSG_IDLE && en->log_entries_first)
		{
			// get, remove and free last log_entry, using its msg address as payload
			struct log_entry** pointerToLast = &en->log_entries_first;
			while ((*pointerToLast)->next)
				pointerToLast = &(*pointerToLast)->next;
			output_message_type = MSG_LOG;
			en->output.message_payload.address = (*pointerToLast)->msg;
			z_free(*pointerToLast);
			*pointerToLast = 0;
		}
		en->output.message_type = output_message_type;
		// finished writing message
		en->output.id = en->input.id + 1;
	}
	dynamic_object_content* next = en->dynamicObject.contents_first;
	*(((u32*)RAM_SEGMENT_TABLE) + 6) = ((u32)en->dynamicObject.address) & 0xFFFFFF;
	while (next)
	{
		if (next->draw) // fixme ? avoid manipulating uninitialized data, but maybe draw should be renamed then
		{
			switch (next->type)
			{
			case TYPE_NONE:
			case TYPE_MODEL:
				break;
			case TYPE_RIG:
				//*
				if (next->rig.play)
					z_skelanime_draw_table(&next->rig.anim);
				//*/
				break;
			}
		}
		else // !draw
		{
			switch (next->type)
			{
			case TYPE_NONE:
			case TYPE_MODEL:
				break;
			case TYPE_RIG:
				//*
				if (!next->rig.play)
				{
					LOG(en, "_z_skelanime_mtx_init(%X, %X, %X, %X, %d, %d, %d)", global, &next->rig.anim, next->rig.skeleton, next->rig.animations[0], 0, 0, 0)
					LOG(en, "table -> %X  address -> %X", *(((u32*)RAM_SEGMENT_TABLE) + 6), en->dynamicObject.address)
					_z_skelanime_mtx_init(global, &next->rig.anim, next->rig.skeleton, next->rig.animations[0], 0, 0, 0);
					z_skelanime_change_anim(&next->rig.anim, next->rig.animations[0], 1, 0, 0, 1, 1);
					next->draw = 1;
					next->rig.play = 1;
				}
				//*/
				break;
			}
		}
		next = next->next;
	}
}

static void dest(entity_t* en, z64_global_t* global) {

}

static void draw(entity_t* en, z64_global_t* global) {
	zh_draw_debug_text(global, 0xFFFFFFFF, 1, 8, "A>P %X / P>A %X", &en->output, &en->input);
	//zh_draw_debug_text(global, 0xFFFFFFFF, 1, 10, "%X", en->dynamicObject.address);
	*(((u32*)RAM_SEGMENT_TABLE) + 6) = ((u32)en->dynamicObject.address) & 0xFFFFFF;
	gSPSegment(global->common.gfx_ctxt->poly_opa.p++, 0x06, en->dynamicObject.address);
	//global->obj_ctxt.objects[en->actor.alloc_index].data = en->dynamicObject.address;
	dynamic_object_content* next = en->dynamicObject.contents_first;
	while (next)
	{
		if (next->draw)
		{
			switch (next->type)
			{
			case TYPE_NONE:
				break;
			case TYPE_MODEL:
				//zh_draw_debug_text(global, 0xFFFFFFFF, 1, 12, "%X %X", en->dynamicObject.address, next->model.dlist);
				z_cheap_proc_draw_opa(global, next->model.dlist);
				break;
			case TYPE_RIG:
				//LOG(en, "anim sk=%X", next->rig.skeleton)
				//zh_draw_debug_text(global, 0xFFFFFFFF, 1, 12, "anim sk=%X", next->rig.skeleton);// crash
				_z_skelanime_draw_mtx(global, next->rig.anim.limb_index, next->rig.anim.draw_table_rot, next->rig.anim.dlist_count, 0, 0, (void*)&en->actor);
				break;
			}
		}
		next = next->next;
	}
}

z64_actor_init_t init_vars = {
	.number = ACT_ID,
	.type = 1,
	.room = 0,
	.flags = 0x00000010,
	.object = OBJ_ID,
	.padding = 0,
	.instance_size = sizeof(entity_t),
	.init = init,
	.dest = dest,
	.main = update,
	.draw = draw
};
