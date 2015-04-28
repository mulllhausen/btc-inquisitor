import sys

previous_text = ""
# specify the total progress meter width in columns (characters), must be int
progress_meter_width = 50

def render(percent, extra_text = ""):
	global previous_text # used to prevent re-rendering the same line of text
	if isinstance(percent, (int, long, float)):
		if percent < 0:
			percent = 0
		if percent > 100:
			percent = 100
		percent_as_cols = int(percent * progress_meter_width / 100.0)
		text = "%06.2f%% [%s] %s" \
		% (
			percent, ("#" * percent_as_cols).ljust(progress_meter_width),
			extra_text
		)
	else: # assume percent is not defined then 
		text = extra_text
	if previous_text == text:
		return # do nothing
	sys.stdout.write("\r%s" % text)
	sys.stdout.flush()
	previous_text = text

def done():
	global previous_text
	# note that print("\n") does not work - it prints two newlines
	sys.stdout.write("\n")
	sys.stdout.flush()
	previous_text = ""

def clear():
	"""clear any previously rendered progress meters"""
	global previous_text # used to prevent re-rendering the same line of text
	if not len(previous_text):
		return
	sys.stdout.write("\r%s\r" % (" " * len(previous_text)))
	del previous_text
