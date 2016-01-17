"""module containing some general mysql-related functions"""

def clean_query(cmd):
    return re.sub("\s+", " ", cmd).strip()
    #return cmd.replace("\n", " ").replace("\t", "").strip()
