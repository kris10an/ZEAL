#!/usr/bin/env python2.6
"""
strtime.py

"""

try:
    import indigo
except ImportError:
    print u"Attachments can only be used from within Indigo"
    raise ImportError
    
from datetime import datetime
from dateutil.relativedelta import relativedelta

def timeToStr(ts=u'now',format=u'long'):

	if format == u'long':
		strFormat = u'%Y-%m-%d %H:%M:%S'
	elif format == u'short':
		strFormat = u'%d.%m %H:%M'
	else:
		raise ValueError(u'Invalid string time format')
		return 0

	try:
		if ts==u'now':
			strtime=datetime.strftime(datetime.now(),strFormat)
		else:
			strtime=datetime.strftime(ts,strFormat)
		return strtime
	except:
		raise RuntimeError(u'Could not create string from time')
		return 0

def timeToVar(var,ts=u'now',format=u'long'):
	try:
		indigoVar=indigo.variables[var]
	except:
		indigoVar=var

	try:
		indigo.variable.updateValue(indigoVar,value=timeToStr(ts,format))
		return 1
	except:
		raise RuntimeError(u'Could not update timestamp variable')
		return 0

def strToTime(str, format=u'long'):
	if format == u'long':
		strFormat = u'%Y-%m-%d %H:%M:%S'
	elif format == u'short':
		strFormat = u'%Y %d.%m %H:%M'
	else:
		raise ValueError(u'Invalid string time format: %s' % (format))
		return 0
	
	try:
		if format == u'short':
			timenow = datetime.now()
			ts = shortTimeToTime(datetime.strptime(datetime.strftime(timenow, u'%Y') + u' ' + str, strFormat)) # No year is included, attempt to find year. Assume that ts is in the past
		else:
			ts = datetime.strptime(str,strFormat)
		return ts
	except:
		raise ValueError(u'Could not get timestamp from string: %s' % (str))
		return 0
		
def varToTime(var, format=u'long'):
	try:
		indigoVar=indigo.variables[var]
	except:
		indigoVar=var

	try:
		ts = strToTime(indigoVar.value, format)
		return ts
	except:
		raise ValueError(u'Could not get timestamp from variable: %s' % str(var))
		return 0
		
def shortTimeToTime(ts):
	timenow = datetime.now()
	ts = ts.replace(year=timenow.year)
	if ts > timenow: #Must be last year, decrease by one year
		#ts = ts.replace(year=timenow.year-1)
		ts = ts - relativedelta(years=1)
	return ts


def timeDiff(td1,td2=u'now',unit=u'all'):
	# Unit :	all|minutes|seconds
	#   """
	#     Difference between date times
	#     If td2 > td1, positive result, otherwise
	#     negative result
	#     """
	if td2 == u'now':
		td2 = datetime.now()
	
	diff = td2 - td1
	if unit == u'all':
		return diff
	elif unit == u'minutes':
		minutes = diff.days*60*24 + int(diff.seconds/60)
		return minutes
	elif unit == u'seconds':
		seconds = diff.days*24*60*60 + diff.seconds
		return seconds
	else:
		raise ValueError(u'Invalid Unit format')
		return 0
		
def varTimeDiff(var1,var2=u'now',format=u'long',unit=u'all'):
	#     """
	#     Difference between time string in two variables
	#     If var2 > var1, positive result, otherwise
	#     negative result
	#     """
	varTime1 = varToTime(var1,format=format)
	if var2 == u'now':
		varTime2 = datetime.now()
	else:
		varTime2 = varToTime(var2,format=format)
		
	return timeDiff(varTime1, varTime2, unit=unit)
		
def prettyDate(time=False):
	#     """
	#     Get a datetime object or a int() Epoch timestamp and return a
	#     pretty string like 'an hour ago', 'Yesterday', '3 months ago',
	#     'just now', etc
	#     """
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time,datetime):
        diff = now - time 
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return u''

    if day_diff == 0:
        if second_diff < 10:
            return u"just now"
        if second_diff < 60:
            return str(second_diff) + u" seconds ago"
        if second_diff < 120:
            return  u"a minute ago"
        if second_diff < 3600:
            return str( second_diff / 60 ) + u" minutes ago"
        if second_diff < 7200:
            return u"an hour ago"
        if second_diff < 86400:
            return str( second_diff / 3600 ) + u" hours ago"
    if day_diff == 1:
        return u" yesterday"
    if day_diff < 7:
        return str(day_diff) + u" days ago"
    if day_diff < 31:
        return str(day_diff/7) + u" weeks ago"
    if day_diff < 365:
        return str(day_diff/30) + u" months ago"
    return str(day_diff/365) + u" years ago"
