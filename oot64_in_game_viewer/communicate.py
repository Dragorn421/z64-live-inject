import time
import socket

from collections import deque

addresses_to_free = []

class MessageType:
    def __init__(self, name, type_id, payload_type=None):
        self.name = name
        self.type_id = type_id
        self.payload_type = payload_type
    def __hash__(self):
        return self.type_id
    def __str__(self):
        return self.name
    def __repr__(self):
        return 'MessageType<%s(%d) %s>' % (self.name, self.type_id, self.payload_type)

MESSAGE = dict()
MESSAGE_BY_TYPE_ID = dict()
for message_type in (
    MessageType('IDLE', 0),
    MessageType('PING', 1),
    MessageType('PONG', 2),
    MessageType('LOG',  3, 'u32'),

    MessageType('MALLOC',        10, 'u32'),
    MessageType('MALLOC_RESULT', 11, 'u32'),
    MessageType('FREE',          12, 'u32'),

    MessageType('CLEAR_OBJECT',                 20),
    MessageType('SET_OBJECT',                   21, 'u32'),
    MessageType('ADD_OBJECT_CONTENT_MODEL',     22, 'u32'),
    MessageType('ADD_OBJECT_CONTENT_ANIMATION', 23, ('u32','u32')),
):
    MESSAGE[message_type.name] = message_type
    MESSAGE_BY_TYPE_ID[message_type.type_id] = message_type

class MutualFeedback:

    def __init__(self, input, output):
        self.input = input
        self.output = output
        self.message_queue = deque()
        self.handlers = dict()
        # fixme hacky reset/memory free
        self.queueMessage(MESSAGE['CLEAR_OBJECT'])
        global addresses_to_free
        for address in addresses_to_free:
            self.queueMessage(MESSAGE['FREE'], address)
        addresses_to_free = []

    def findActor(self, actorType, actorId, actorCtx):
        # hardcoded offsets for mq debug, every version should have the same actor struct though
        # (apart from the debug padding, that we don't care about here)
        actorListEntry = actorCtx + 0x000C + actorType * 0x08 # actorCtx.actorList[actorType]
        n = self.get(actorListEntry + 0, 'u32') # actorListEntry.length
        actor = self.get(actorListEntry + 4, 'u32') # actorListEntry.first
        #print('n =', n)
        #print('first =', hex(actor))
        for i in range(n):
            id = self.get(actor + 0, 'u32') >> 16 # actor.id (fixme it's a s16, not u32, shifting for now)
            #print(i, 'actor =', hex(actor), 'id =', id)
            if id == actorId:
                self.input = actor + (0x8023548C - 0x80235340)
                self.output = actor + (0x802354A8 - 0x80235340)
            actor = self.get(actor + 0x124, 'u32') # actor.next
        print('Using input =', hex(self.input), ' output =', hex(self.output))

    def queueMessage(self, message_type, payload=None):
        if message_type.payload_type and payload is None:
            print('Ignoring message without payload for', message_type)
            return
        if not message_type.payload_type and payload is not None:
            print('Ignoring useless payload for', message_type, '(message still going through)')
            payload = None
        self.message_queue.append((message_type, payload))

    def queueHandler(self, message_type, handler):
        type_handlers = self.handlers.get(message_type)
        if type_handlers is None:
            type_handlers = deque()
            self.handlers[message_type] = type_handlers
        type_handlers.append(handler)

    def request(self, data, read=False):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        attempts = 0
        while True:
            try:
                s.connect(('127.0.0.1', 80))
                break
            except ConnectionRefusedError as e: # todo check for errno 111, very likely due to "pj64 slow"
                attempts += 1
                if attempts >= 20:
                    raise e
                time.sleep(0.1)
        s.send(data)
        if read:
            r = s.recv(4096)
        s.close()
        if read:
            return r

    def get(self, address, type):
        req = 'get %s 0x%X' % (type, address)
        #print('req =', req)
        res = self.request(req.encode(), read=True)
        if type.startswith('u'):
            return int(res)
        if type == 'str':
            return res.decode()
        return res

    def set(self, address, type, v):
        if type == 'bytes':
            req = 'set bytes 0x%X ' % address
            req = req.encode()
            n = len(req)
            n += len(('%d' % n).encode()) + 2
            req += ('%d ' % n).encode()
            if len(req) > n:
                print('CANNOT SET BYTES!!!', req, n) # fixme ?
                return
            if len(req) < n:
                req += b' ' * (n - len(req))
            req += v
            self.request(req)
        else:
            req = 'set %s 0x%X %d' % (type, address, v) # fixme %d assumes v is integer
            #print('req =', req)
            self.request(req.encode())

    def tick(self):
        idle = True
        input_id = self.get(self.input, 'u32')
        output_id = self.get(self.output, 'u32')
        # if it's our turn to write
        if input_id > output_id:
            # get input data
            input_message_type_id = self.get(self.input + 4, 'u32')
            input_message_type = MESSAGE_BY_TYPE_ID.get(input_message_type_id)
            if input_message_type:
                if input_message_type.payload_type:
                    if isinstance(input_message_type.payload_type, tuple):
                        # fixme untested, useless rn
                        for i in range(len(input_message_type.payload_type)):
                            if input_message_type.payload_type[i] != 'u32':
                                # todo
                                raise ValueError('Unknown size of payload type %r (only u32 implemented)' % input_message_type.payload_type[i])
                            input_message_payload = self.get(self.input + 8 + i * 4, input_message_type.payload_type[i])
                    else:
                        input_message_payload = self.get(self.input + 8, input_message_type.payload_type)
                    # process input data
                    output_message = self.process(input_message_type, input_message_payload)
                else:
                    output_message = self.process(input_message_type)
                # set output data
                print('output_message = %r' % (output_message,))
                if isinstance(output_message, tuple):
                    output_message_type, output_message_payload = output_message
                    if isinstance(output_message_type.payload_type, tuple):
                        # assume output_message_payload to be a tuple of the right size
                        for i in range(len(output_message_type.payload_type)):
                            if output_message_type.payload_type[i] != 'u32':
                                # todo
                                raise ValueError('Unknown size of payload type %r (only u32 implemented)' % output_message_type.payload_type[i])
                            input_message_payload = self.set(self.output + 8 + i * 4, output_message_type.payload_type[i], output_message_payload[i])
                    else:
                        self.set(self.output + 8, output_message_type.payload_type, output_message_payload)
                else:
                    output_message_type = output_message
            else:
                print('Unknown input_message_type_id =', input_message_type_id)
                output_message_type = MESSAGE['IDLE']
            idle = output_message_type.name == 'IDLE'
            self.set(self.output + 4, 'u32', output_message_type.type_id)
            # set id when done writing
            self.set(self.output, 'u32', input_id + 1)
        return idle

    def process(self, input_message_type, input_payload=None):
        handler_queue = self.handlers.get(input_message_type)
        if handler_queue:
            print(input_message_type.name)
            handler = handler_queue[0]
            if not (handler() if input_payload is None else handler(input_payload)):
                handler_queue.popleft()
        elif input_message_type.name == 'IDLE':
            pass
        elif input_message_type.name == 'PING':
            print('PING')
            self.queueMessage(MESSAGE['PONG'])
        elif input_message_type.name == 'LOG':
            print('LOG', self.get(input_payload, 'str'))
            self.queueMessage(MESSAGE['FREE'], input_payload)
        else:
            print('Unhandled (no handler for) message', input_message_type, 'with payload', input_payload)
            if input_message_type.name == 'MALLOC_RESULT':
                print('Adding (unused?) address', input_payload, 'of MALLOC_RESULT to addresses_to_free...')
                addresses_to_free.append(input_payload)
        if not self.message_queue:
            return MESSAGE['IDLE']
        message_type, payload = self.message_queue.popleft()
        if payload is not None:
            return message_type, payload
        else:
            return message_type

    def ping(self, text):
        print('ping(%r)' % text)
        self.queueMessage(MESSAGE['PING'])
        def pongHandler():
            print('PONG', text)
        self.queueHandler(MESSAGE['PONG'], pongHandler)

    def setObject(self, data, callback):
        print('setObject')
        self.queueMessage(MESSAGE['MALLOC'], len(data))
        def copyData(address):
            addresses_to_free.append(address)
            print('copying to', hex(address))
            self.set(address, 'bytes', data)
            self.queueMessage(MESSAGE['SET_OBJECT'], address)
            callback()
        self.queueHandler(MESSAGE['MALLOC_RESULT'], copyData)

    def addObjectModelOffset(self, offset):
        print('addObjectModelOffset')
        self.queueMessage(MESSAGE['ADD_OBJECT_CONTENT_MODEL'], offset)

    def addObjectAnimOffset(self, skeletonOffset, animOffset):
        print('addObjectAnimOffset')
        self.queueMessage(MESSAGE['ADD_OBJECT_CONTENT_ANIMATION'], (skeletonOffset, animOffset))

    def loadObject(self, data, models=None, animations=None):
        def sendOffsets():
            if models:
                for model in models:
                    self.addObjectModelOffset(model)
            if animations:
                for skeleton, skeleton_animations in animations.items():
                    for animation in skeleton_animations:
                        self.addObjectAnimOffset(skeleton, animation)
        self.setObject(data, callback=sendOffsets)

"""
todo

better init code: make two values right after actor struct always be input/output offsets (must have both because payload struct size may vary)

make a nicer logging facility actor-side
    logging really should be a separate thing anyway so queued logs arent lost on crashs
    option 1) logs are stored in a linked list, actor appends to it when writing, plugin removes what it read
        but plugin needs to call actor for z_free anyway... hence option 2
    option 2) logs are stored in a linked list, entries have a "read" flag that allows the actor to "garbage-collect" such now-useless entries, and the plugin to not read the same thing twice. the plugin only sets "read" when entry is read and only does that. garbage-collecting could be done at any point, what would make most sense is on LOG() calls: simple and ensures cleanup right before more memory usage
        no "entry being written" and concurrent access issue if the entries are only appended after being fully built
a nice feature would be "watches", to replace zh_draw_debug_text which carries issues, those wouldnt be single short-lived entries but permanent entries (eg updated every frame but not necessarily), and be stored somewhere else, and not displayed as a single line every read
    but how to prevent the plugin from reading a watch being written? (concurrent access) could just shrug it off since the watch supposedly is updated every frame and there's little chance a concurrent access may happen, and it wouldnt be an issue anyway (?)
make a standalone logging facility

write protocol specification

fix memory management (clear/free)

controls: in blender (+++, sync? eg animation frame), web interface (-)

99% (really, about 4-8 seconds total) of the time spent is sending/receiving data to/from the actor, that should (must / has to) be improved by a lot
"""
