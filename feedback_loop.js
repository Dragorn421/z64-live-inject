const _strongBackingReferences = (function() {
    const _references = [];
    const noop = function () { };

    return {
        "add": function _strongBackingReferences_add(obj)
        {
            _references.push(obj);
        },
        "remove": function _strongBackingReferences_remove(obj)
        {
            const index = _references.indexOf(obj);
            if (index !== -1)
            {
                _references.splice(index, 1);
            }
        },
        "singleUseCallback": function _strongBackingReferences_singleUseCallback(callback)
        {
            if (callback === undefined)
            {
                return noop;
            }

            const singleUseCallback = function ()
            {
                callback.apply(undefined, arguments);
                _strongBackingReferences.remove(callback);
            };

            _strongBackingReferences.add(singleUseCallback);
            return singleUseCallback;
        }
    };
}) ();

// function Server(settings) https://github.com/project64/project64/blob/760a3d6b0065387ec9232a8bc8c871f66c41d2f4/Source/Project64/UserInterface/API.js#L960
// "sockAccept", js_ioSockAccept https://github.com/project64/project64/blob/0462f637c4794eb99d81d98b569806f0ff107e89/Source/Project64/UserInterface/Debugger/ScriptInstance.h#L238
// js_ioSockAccept https://github.com/project64/project64/blob/0462f637c4794eb99d81d98b569806f0ff107e89/Source/Project64/UserInterface/Debugger/ScriptInstance.cpp#L684
// AcceptEx https://docs.microsoft.com/en-us/windows/win32/api/mswsock/nf-mswsock-acceptex
// tldr waiting new sockets is blocking, this is copied from the pj64 source code but will try wrapping AcceptEx to not inconditionally accept
function Server(settings)
{
    var _this = this;
    var _fd = _native.sockCreate()
    var _listening = false;
    var _queued_accept = false;

    var _onconnection = function(socket){}

	var sockAccept_wrapper = function(fd, callback) {
		console.log('sockAccept_wrapper');
		_native.sockAccept(fd, callback);
	}

    this.listen = function (port) {
        if (_native.sockListen(_fd, port || 80)) {
            _listening = true;
        } else {
            throw new Error("failed to listen");
        }

        if (_queued_accept) {
            sockAccept_wrapper(_fd, _strongBackingReferences.singleUseCallback(_acceptClient));
        }
    }
    
    if(settings.port)
    {
        this.listen(settings.port || 80);
    }
    
    // Intermediate callback
    //  convert clientFd to Socket and accept next client
    var _acceptClient = function(clientFd)
    {
        _onconnection(new Socket(clientFd))
        sockAccept_wrapper(_fd, _strongBackingReferences.singleUseCallback(_acceptClient))
    }
    
    this.on = function(eventType, callback)
    {
        switch(eventType)
        {
        case 'connection':
            _onconnection = callback;
            if (_listening) {
                sockAccept_wrapper(_fd, _strongBackingReferences.singleUseCallback(_acceptClient));
            } else {
                _queued_accept = true;
            }
            break;
        }
    }
}



var server = new Server({port: 80});

log = console.log // todo redirect logs to python

function handleIncoming(data) {
	log('Got:', data);
	var args = String(data).split(' ');
	//log(' ->', args);
	// action
	action = args[0]
	if (action != 'get' && action != 'set') {
		log('Unknown action', action, '(expected "get" or "set")')
		return;
	}
	//log('action =', action);
	// args.length
	if (action == 'get' && args.length != 3) {
		log('Expected 3 arguments total for action "get", not', args.length, '(get dataType address)');
		return;
	}
	else if (action == 'set' && !(args.length == 4 || (args.length >= 5 && args[1] == 'bytes'))) {
		log('Expected 4 (or 5 for type bytes) arguments total for action "set", not', args.length, '(set dataType address value, or set bytes address startInData <value...>)');
		return;
	}
	// address
	var address = parseInt(args[2]);
	if (isNaN(address)) {
		log('Could not parse address', args[2], 'as integer')
		return;
	}
	//log('address =', '0x' + address.hex());
	// dataType
	dataType = args[1]
	switch(dataType)
	{
	case 'bytes':
		if (action == 'set') {
			var start = parseInt(args[3]);
			if (isNaN(start)) {
				log('Could not parse bytes start', args[3], 'as integer')
				return;
			}
			if (start < 0) {
				log('Parsed bytes start', args[3], 'as integer to', start, 'which is negative but this must be a (positive) offset')
				return;
			}
			//log('(set) value =', value);
			for (var i=0;start+i<data.length;i++)
				mem.u8[address+i] = data[start+i];
		} else {
			log('"get bytes" unsupported rn');
			return;
		}
		break;
	case 'u32':
		if (action == 'set') {
			var value = parseInt(args[3]);
			if (isNaN(value)) {
				log('Could not parse value', args[3], 'as integer')
				return;
			}
			if (value < 0) {
				log('Parsed value', args[3], 'as integer to', value, 'which is negative but this is a u32')
				return;
			}
			//log('(set) value =', value);
			mem.u32[address] = value;
		} else {
			var value = mem.u32[address];
			//log('(get) value =', value);
			return value;
		}
		break;
	case 'str':
		if (action == 'set') {
			log('"set str" unsupported rn');
			return;
		} else {
			var value = mem.getstring(address);
			log('(get) value =', value);
			return value;
		}
		break;
	default:
		log('Unknown dataType', dataType, '(expected "u32")')
		return;
	}
}

server.on('connection', function(socket) {
	socket.on('data', function(data) {
		try {
			out = handleIncoming(data);
			if (out != undefined) {
				socket.write(out);
			}
		} catch(e) {
			log(e); // fixme test
		}
	});
});

/*
// reads "address"
// writes "value_at_address_as_u32 "
server.on('connection', function(socket) {
	socket.on('data', function(data) {
		console.log(data);
		var address = parseInt(data);
		console.log(address);
		var value = mem.u32[address];
		console.log(value);
		socket.write(value);
		socket.write(' ');
	});
});
//*/

/*

MSG_IDLE = 0
MSG_PING = 1
MSG_PONG = 2

const Message = mem.typedef(
{
	id: u32,
	message_type: u32
	// ...
});

input = new Message(0x802352FC); // actor -> plugin
output = new Message(0x80235318); // plugin -> actor

function loop()
{
	if (input.id > output.id)
	{
		switch (input.message_type)
		{
		case MSG_IDLE:
			output.message_type = MSG_IDLE;
			break;
		case MSG_PING:
			console.log('PING');
			output.message_type = MSG_PONG;
			break;
		case MSG_PONG:
			console.log('PONG');
			output.message_type = MSG_IDLE;
			break;
		}
		output.id = input.id + 1;
	}
}

setInterval(loop, 1000);

*/
