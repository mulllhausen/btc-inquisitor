#!/usr/bin/env python2.7
# parse the readme.json file into github.com's README.md format
# run like so: ./generate_github_readme.py > README.md

import json, collections, textwrap

with open("readme.json", "r") as file:
	readme_json = file.read()
file.close()

right_col = 110 # text goes no further than this many chars across the page
codeblock_indent = "    "

readme_dict = json.loads(readme_json, object_pairs_hook = collections.OrderedDict)
for (heading, val) in readme_dict.items():
	if heading == "name":
		print val + "\n==========\n"
	if heading in ["synopsis", "description", "warnings", "notes", "author"]:
		print "%s\n----------\n\n%s\n" % (heading.upper(), ((codeblock_indent + val) if heading == "synopsis" else val))
	if heading == "options":
		print heading.upper() + "\n----------\n"
		for option in val:
			option_str = codeblock_indent # reset
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
				option_str = option_str + "\n\n" + option["help"] + "\n\n\n"
			print option_str
