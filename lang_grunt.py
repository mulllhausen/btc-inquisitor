"""module containing some general language-related functions"""

# module globals:
n = "\n"

def die(message = False):
	if message == False:
		sys.exit(0)
	else:
		sys.exit(n + message)

def warn(options, message):
	if options.NOWARN:
		return
	print "[warn] %s" % message

def list2human_str(the_list, final_seperator = "and"):
	"""convert a python list instance to english"""

	if not the_list:
		return ""

	if len(the_list) == 1:
		return the_list[0]

	return "%s %s %s" % (", ".join(the_list[: -1]), final_seperator,
	the_list[-1])
