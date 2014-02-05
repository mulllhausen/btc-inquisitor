import sys

def render(value):
	global previous_value, previous_text # used to prevent re-rendering the same line of text
	if isinstance(value, (int, long)):
		# expects value to be a percentage (ie 0 - 100)
		if value < 0:
			value = 0
		if value > 100:
			value = 100
		try:
			if previous_value == value:
				return # do nothing
		except: # previous_value not yet defined
			pass
		text = "%3.0f%% [%s]" % (value, ("#" * value).ljust(100))
	else:
		try:
			if previous_text == value:
				return # do nothing
		except: # previous_line not yet defined
			pass
		text = value
	sys.stdout.write("\r%s" % text)
	sys.stdout.flush()
	previous_value = value
	previous_text = text

def done():
	global previous_value, previous_text
	sys.stdout.write("\n") # note that print("\n") does not work - it prints two newlines
	sys.stdout.flush()
	del previous_value, previous_text

def clear():
	"""clear any previously rendered progress meters"""
	global previous_value, previous_text # used to prevent re-rendering the same line of text
	try:
		sys.stdout.write("\r%s\r" % (" " * len(previous_text)))
		del previous_value, previous_text
	except: # previous_value and previous_text not yet defined
		pass
