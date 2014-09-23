"""module containing some general language-related functions"""

import sys
import os

# module globals:

def die(message = False):
	if message == False:
		sys.exit(0)
	else:
		sys.exit("%s%s" % (os.linesep, message))

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

	return "%s %s %s" % (
		", ".join(the_list[: -1]), final_seperator, the_list[-1]
	)

def plural(word, count):
	"""return the given word as plural or singular"""
	if word == "s":
		return "s" if (count > 1) else ""
	if word == "have":
		return "have" if (count > 1) else "has"
	die("unrecognized word '%s'" % word)
