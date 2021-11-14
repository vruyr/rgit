_command_handlers = {}


def command(*names):
	def decorator(handler):
		name = names[0]
		if name in _command_handlers:
			raise ValueError("command already registered")
		_command_handlers[name] = (names[1:], handler)
		return handler
	return decorator


def enumerate_command_handlers():
	for name, (aliases, handler) in _command_handlers.items():
		yield (name, aliases, handler)


def get_command_handler(name):
	if name not in _command_handlers:
		return None
	return _command_handlers[name][1]
