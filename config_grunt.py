"""module containing functions to read and translate the config file"""

import json, os, socket

# see the end of this file for the initializations

def translate(translate_this_dict = None, translation_round = None):
    """
    loop through all the elements in config.json and perform substitutions. you
    should call this function without arguments. the arguments are used when
    this function calls itself recursively.

    two rounds of translation are done on the config dict:
    - round 1 - first pass of the dict. expand relative filepaths to absolute.
    - round 2 - perform substitutions.
    """
    global config_dict
    if translate_this_dict is None:
        config_dict = translate(config_dict, 1)
        config_dict = translate(config_dict, 2)
    else:
        for (k, v) in translate_this_dict.items():
            if isinstance(v, dict):
                v = translate(v, translation_round)
            elif isinstance(v, basestring):
                if translation_round == 1:
                    if k == "base_dir":
                        v = os.path.join(os.path.expanduser(v), "")
                elif translation_round == 2:
                    if "@@base_dir@@" in v:
                        v = substitute_base_dir(v)
                    if "@@hostname@@" in v:
                        v = substitute_hostname(v)

            translate_this_dict[k] = v

        return translate_this_dict

def substitute_base_dir(v):
    try:
        v = v.replace("@@base_dir@@", config_dict["base_dir"])
    except:
        raise Exception(
            "cannot translate @@base_dir@@ in the config dict because it"
            " is not defined in the config dict"
        )
    # normpath converts // to / but also removes any trailing slashes
    return os.path.normpath(v)

def substitute_hostname(v):
    hostname = socket.gethostname().strip()
    if hostname == "":
        raise Exception(
            "This machine has no hostname. You must set one to use this"
            " program."
        )
    return v.replace("@@hostname@@", hostname)

with open("config.json") as config_file:
    config_dict = json.load(config_file)
config_dict = translate(config_dict)
