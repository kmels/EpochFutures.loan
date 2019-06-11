def term_pretty(seconds):
    hour = 3600
    day = 3600*24
    if seconds < hour:
        return "%dm" % (seconds/60)
    if seconds < day:
        return "%dh" % (seconds/3600)
    return "%dd" % (seconds/day)

def term_seconds(term):
    parts = term.split(".")
    
    if len(parts) == 1:
        days = 0
        subparts = parts[0].split(":")
    else:
        days = int(parts[0])
        subparts = parts[1].split(":")

    hours = int(subparts[0])
    minutes = int(subparts[1])
        
    return (days*1440 + hours*60 + minutes)*60
