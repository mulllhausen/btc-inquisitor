#!/usr/bin/env python2.7
# parse the readme.json file into a linux manpage format
# run like so: ./generate_manpage.py > manpage.txt

import json, collections, textwrap

with open("readme.json", "r") as file:
	readme_json = file.read()
file.close()

right_col = 110 # text goes no further than this many chars across the page
indent = "       "

readme_dict = json.loads(readme_json, object_pairs_hook=collections.OrderedDict)
for (heading, val) in readme_dict.items():
	if heading in ["name", "synopsis", "description", "warnings", "notes", "author"]:
		print heading.upper()
		for line in val.split("\n\n"):
			print indent + ("\n" + indent).join(textwrap.wrap(line, (right_col - len(indent)))) + "\n"
	if heading == "options":
		print heading.upper()
		for option in val:
			option_str = indent # reset
			if "short_arg" in option:
				option_str = option_str + option["short_arg"]
				if "dest" in option:
					option_str = option_str + " " + option["dest"] + ", "
				else:
					option_str = option_str + ", "
			if "long_arg" in option:
				option_str = option_str + option["long_arg"]
				if "dest" in option:
					option_str = option_str + "=" + option["dest"]
			if "help" in option:
				for line in option["help"].split("\n\n"):
					option_str = option_str + "\n" + indent + indent + ("\n" + indent + indent).join(textwrap.wrap(line, (right_col - len(indent + indent)))) + "\n"
			print option_str
