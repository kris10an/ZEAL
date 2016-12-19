#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import indigo

import os
import sys
import logging
import json
#import csv,codecs,cStringIO
from csvUnicode import unicodeReader, unicodeWriter, UTF8Recoder

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

zDefs = {
	u"0x71"						: {
		u"description"			: u"Notification command class",
		u"eventName"			: u"Received notification/alarm command",
		u"file"					: u"0x71CC.csv",
		u"byteDescription"		: {8:u"Notification report", 9:u"Alarm type", 10:u"Alarm level", 11:u"Reserved", 12:u"Notification status", 13:u"Notification type", 14:u"Event", 15:u"Event parameters length"},
		u"types"				: {}
		}
	}
	
zFolder = u"Z-Wave"

########################################
# Tiny function to convert a list of integers (bytes in this case) to a
# hexidecimal string for pretty logging.
def convertListToHexStr(byteList):
	return ' '.join([u"%02X" % byte for byte in byteList])
	
########################################
# Tiny function to convert a list of integers (bytes in this case) to a
# hexidecimal list (string formatted) 
def convertListToHexStrList(byteList):
	return [u"0x%02X" % byte for byte in byteList]
	
########################################
# Safely get keys from dictionary
def safeGet(dct, defaultVal, *keys):
    for key in keys:
        try:
            dct = dct[key]
        except KeyError:
            return defaultVal
    return dct
    


################################################################################
class Plugin(indigo.PluginBase):

	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.errorState = False
	
		# Set plugin preferences
		self.setUpdatePluginPrefs()
		
		self.zDefs = zDefs
		
		self.tempFilter = {} # Temporary filter values, for use in UI dialog before storing to valuesDict
		
		

	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)
				
	########################################
	def startup(self):
		self.logger.debug(u"startup called")
		
		self.zNodes = {} # Map of zwave nodes to indigo devices
		
		# get Z-wave defs, types and events from file
		self.getZwaveDefs()
		
		# map z-wave nodes to indigo devices
		self.getZwaveNodeDevMap()
		#self.logger.debug(self.zNodes)
		
		indigo.zwave.subscribeToIncoming()
		#indigo.zwave.subscribeToOutgoing()
		
	########################################
	def shutdown(self):
		self.logger.debug(u"shutdown called")
		
	#####
	# Set or update plugin preferences
	# 	running 		: True if plugin is already running and prefs are to be changed
	#
	def setUpdatePluginPrefs(self, running = False):
		self.logger.debug(u'CALL setUpdatePluginPrefs, running: %s' % unicode(running))
		
		# Set log levels
		if running: setText = u'Changing'
		else: setText = u'Setting'
		self.indigo_log_handler.setLevel(self.pluginPrefs.get(u'logLevel', u'INFO'))
		self.plugin_file_handler.setLevel(u'DEBUG')
		self.ed = self.pluginPrefs.get(u'extensiveDebug', False)
		self.logger.info(u'%s log level to %s' % (setText, self.pluginPrefs.get(u'logLevel', u'INFO')))
		self.logger.debug(u'Extensive debug logging set to %s' % unicode(self.ed))
		self.logger.debug(u'%s file handler log level to DEBUG' % (setText))
		# DEBUG		: All debug info
		# INFO		: Informational messages relevant to the user
		# WARNING	: More critical information to the user, warnings
		# ERROR		: Errors not critical for plugin execution
		# CRITICAL	: Errors critical for plugin execution, plugin will stop
		
	########################################
	# If runConcurrentThread() is defined, then a new thread is automatically created
	# and runConcurrentThread() is called in that thread after startup() has been called.
	#
	# runConcurrentThread() should loop forever and only return after self.stopThread
	# becomes True. If this function returns prematurely then the plugin host process
	# will log an error and attempt to call runConcurrentThread() again after several seconds.
	def runConcurrentThread(self):
		try:
			while True:
				#self.getZwaveNodeDevMap()
				#self.logger.debug(u'runConcurrentThread 20')
				self.sleep(20)
		except self.StopThread:
			pass

	########################################
	def zwaveCommandReceived(self, cmd):
		byteList = cmd['bytes']			# List of the raw bytes just received.
		byteListStr = convertListToHexStr(byteList)
		byteListHexStr = convertListToHexStrList(byteList)
		nodeId = cmd['nodeId']			# Can be None!
		endpoint = cmd['endpoint']		# Often will be None!
		CC = byteListHexStr[7] 			# Command class
		
		#self.logger.debug(byteListHexStr)
		
		if CC in self.zDefs:
			self.logger.debug(u"received: %s (node %03d, endpoint %s)" % (byteListStr, nodeId, endpoint))
			self.logger.debug(u'Command class:		%s (%s)' % (CC, self.zDefs[CC][u'description']))
			self.logger.debug(u'Command:			%s' % (byteList[8]))
			self.logger.debug(u'V1 Alarm Type:		%s' % (byteList[9]))
			self.logger.debug(u'V1 Alarm Level:		%s' % (byteList[10]))
			self.logger.debug(u'Notification Status: %s' % (byteList[12]))
			self.logger.debug(u'Notification Type:	%s (%s)' % (byteList[13], self.zDefs[CC][u'types'][byteListHexStr[13]][u'description']))
			#self.logger.debug(u'Event:				%s (%s)' % (byteList[14], self.zDefs[CC][u'types'][byteListHexStr[13]][u'events'][byteListHexStr[14]][u'description']))
			self.logger.debug(u'Event:				%s (%s)' % (byteList[14], safeGet(self.zDefs, u'Unknown Event', CC, u'types', byteListHexStr[13], u'events', byteListHexStr[14], u'description')))
			if len(byteList) >= 18:
				eventParmStr = u''
				i = 16
				while i < len(byteList)-1:
					eventParmStr = eventParmStr + unicode(byteList[i])
					i += 1
				self.logger.debug(u'Event Parameters:	%s' % (eventParmStr))
		
			#self.logger.error(u'error')
			
		
		# 			self.logger.debug(u'endpoint: %s, type: %s' % (endpoint, type(endpoint)))
		# 
		# 			if nodeId and endpoint:
		# 				self.debugLog(u"received: %s (node %03d, endpoint %s)" % (byteListStr, nodeId, endpoint))
		# 			elif nodeId:
		# 				self.debugLog(u"received: %s (node %03d)" % (byteListStr, nodeId))
		# 			else:
		# 				self.debugLog(u"received: %s" % (byteListStr))

	def zwaveCommandSent(self, cmd):
		byteList = cmd['bytes']			# List of the raw bytes just sent.
		byteListStr = convertListToHexStr(byteList)
		timeDelta = cmd['timeDelta']	# The time duration it took to receive an Z-Wave ACK for the command.
		cmdSuccess = cmd['cmdSuccess']	# True if an ACK was received (or no ACK expected), false if NAK.
		nodeId = cmd['nodeId']			# Can be None!
		endpoint = cmd['endpoint']		# Often will be None!

		if cmdSuccess:
			if nodeId:
				self.debugLog(u"sent: %s (node %03d ACK after %d milliseconds)" % (byteListStr, nodeId, timeDelta))
			else:
				self.debugLog(u"sent: %s (ACK after %d milliseconds)" % (byteListStr, timeDelta))
		else:
			self.debugLog(u"sent: %s (failed)" % (byteListStr))

	#####
	# Read Z-wave commands and defs from supporting files
	#
	def getZwaveDefs(self):
		# 0x71 Notification/alarm command class
		
		try:
			x71file = zFolder + u'/' + self.zDefs[u'0x71'][u'file']
			self.logger.debug(u'Reading file %s' % (x71file))
			with open(x71file,'r') as fin:
				reader = unicodeReader(fin, dialect='excel', delimiter=';')
				header = next(reader)
				t=self.zDefs[u'0x71'][u'types']
				for row in reader:
					if not row[0] in t:
						t[row[0]] = {}
						t[row[0]][u'description'] = row[1]
						t[row[0]][u'version'] = row[2]
						t[row[0]][u'events'] = {}

					e = t[row[0]][u'events']
					if not row[3] in e:
						e[row[3]] = {}
						e[row[3]]['description'] = row[4]
						e[row[3]]['version'] = row[5]
						e[row[3]]['parameterText'] = row[6]
					else:
						self.logger.error(u'Duplicate notification event in file %s, misconfiguration' % (x71file))					
						
		except IOError:
			self.logger.critical(u'Could not read file %s' % (x71file))
			self.errorState = True	
		except:
			self.logger.critical(u'Unexpected error while reading file %s' % (x71file))
			self.errorState = True
			raise
		else:
			self.logger.debug(u"Successfully read file '%s'" % (x71file))
			#self.logger.debug(self.zDefs)
			
	#####
	# Map Z-wave nodes to devices
	#
	def getZwaveNodeDevMap(self):
		self.logger.debug(u'Mapping Z-wave nodes to indigo devices')
		# get all nodes already in zNodes, avoid to have to delete zNodes dict and temporarily risk having empty zNodes dict
		tmpNodes = set()
		for node in self.zNodes:
			tmpNodes.add(node)
		
		# add all endpoints to zNodes
		#self.logger.debug(tmpNodes)
		nSkipped = 0
		for dev in indigo.devices.iter('indigo.zwave'):

			endpoint = dev.ownerProps.get('zwDevEndPoint')

			if not dev.enabled:
				if self.ed: self.logger.debug(u'Skipping device id %s "%s" with endpoint %s - device disabled' % (unicode(dev.id), unicode(dev.name), endpoint))
				nSkipped += 1
				continue

			if not dev.address in self.zNodes:
				self.zNodes[dev.address] = {}
			
			#Check if this device has lower subindex, then replace previous device
			#important with = below, to update existing devices
			if not endpoint in self.zNodes[dev.address] or (dev.ownerProps.get('zwDevSubIndex') <= self.zNodes[dev.address][endpoint].ownerProps.get('zwDevSubIndex')):
				if not endpoint in self.zNodes[dev.address]: replaceStr = u'New add'
				else: replaceStr = u'Replaced: lower sub index'
				if self.ed: self.logger.debug(u'Mapping device id %s "%s" with endpoint %s - %s' % (unicode(dev.id), unicode(dev.name), unicode(endpoint), replaceStr))
				self.zNodes[dev.address][endpoint] = dev
				tmpNodes.discard(dev.address)
			else:
				if self.ed: self.logger.debug(u'Skipping device id %s "%s" with endpoint %s - higher subIndex' % (unicode(dev.id), unicode(dev.name), unicode(endpoint)))
			
		
		# Check if some z-wave devices might have been deleted or disabled since last update, and remove those from zNodes
		for node in tmpNodes:
			if node in self.zNodes:
				del self.zNodes[node]
				if self.ed: self.logger.debug(u'Removed node %s from zNodes dict' % (unicode(node)))
				
		# FIX
		# Workaround, some devices send with endpoint None, while none of the Indigo devices have endpoint None (i.e. two devices
		# with endpoint 1 and 2
		for node in self.zNodes:
			if 1 in self.zNodes[node] and not None in self.zNodes[node]:
				# Has endpoint 1, but not None, copy 1 to None
				self.zNodes[node][None] = self.zNodes[node][1]
				if self.ed: self.logger.debug(u'Device id %s "%s" has no device with endpoint None - copied from 1' % (unicode(dev.id), unicode(dev.name)))
		
		self.logger.info(u'Finished mapping %s z-wave nodes to indigo devices. Skipped %s disabled devices' % (unicode(len(self.zNodes)), unicode(nSkipped)))
		#if self.ed: self.logger.debug(u'zNodes dict:\n%s' % unicode(self.zNodes))
		
	########################################
	# Actions
	########################################

	def testAction(self, action, test1):
		self.logger.debug(u"%s" % unicode(action))
		self.logger.debug(u"%s" % unicode(test1))

	########################################
	# UI List generators and callbackmethods
	########################################
	
	# X71 trigger/event
	# x71received

	# get available filters 
	def getTriggerList(self, filter="", valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL getTriggerFilters')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		if self.ed: self.logger.debug(u'filter: %s' % filter)
		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
		if self.ed: self.logger.debug(u'targetId: %s' % targetId)
		
		if filter in [u'includeFilters']:
			myArray = [
				(u"_blank",u" "),
				(u"_createNew",u"Create new filter...")]
		elif filter in [u'alarmTypes', u'events']:
			myArray = [
				(u"all",u"All")]
			
		if filter == u'includeFilters':
			if u'includeFilters' in valuesDict:
				if self.ed: self.logger.debug(u'includeFilters: %s' % unicode(valuesDict[u'includeFilters']))
				includeFilters = self.load(valuesDict.get(u'includeFilters', self.store(list())))
				for filterNum, filterDict in enumerate(includeFilters):
					#self.logger.debug(u'k: %s, v: %s' % (k,v))
					myArray.append( (filterNum,filterDict['name']) )
		elif filter == u'alarmTypes':
			for cmdType, cmdTypeDict in self.zDefs[u'0x71'][u'types'].items():
				myArray.append( (cmdType,safeGet(cmdTypeDict, u'%s - Unspecified type' % unicode(cmdType), u'description')) ) 
		elif filter == u'events':
			if valuesDict[u'selectedIncludeTypes'] == u'all':
				if self.ed: self.logger.debug(u'Selected all alarm types')
			elif not valuesDict[u'selectedIncludeTypes'] in self.zDefs[u'0x71'][u'types']:
				self.logger.warn(u'Invalid or no selected alarm/notification type')
			else:
				for event, eventDict in self.zDefs[u'0x71'][u'types'][valuesDict[u'selectedIncludeTypes']][u'events'].items():
					myArray.append( (event,unicode(event) + u' - ' + safeGet(eventDict, u'Unspecified event', u'description')) )
					
		if self.ed: self.logger.debug(u'myArray: %s' % unicode(valuesDict))

		return myArray	
		
	def selectedTriggerFilterChangedSelection(self, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL selectedTriggerFilterChangedSelection')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
		if self.ed: self.logger.debug(u'targetId: %s' % targetId)

		if valuesDict[u'selectedIncludeFilter'] == u'_createNew' or valuesDict[u'selectedIncludeFilter'] == u'_blank':
			if self.ed: self.logger.debug(u'New filter selected, clearing values from UI')
			valuesDict[u'includeFilterName'] = u''
			valuesDict[u'selectedIncludeTypes'] = u''
			valuesDict[u'selectedIncludeEvents'] = u''
	
		#self.logger.debug(u'return valuesDict: %s' % unicode(valuesDict))
		return valuesDict
		
		
	def selectedTriggerFilterChangedIntSelection(self, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL selectedTriggerFilterChangedIntSelection')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
		if self.ed: self.logger.debug(u'targetId: %s' % targetId)
	
		#self.logger.debug(u'return valuesDict: %s' % unicode(valuesDict))
		return valuesDict
		
	def selectedTriggerIncludeFilterSave(self, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL selectedTriggerIncludeFilterSave')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		
		errorMsg = ''

		if valuesDict[u'selectedIncludeFilter'] == u'_createNew': # Saving new filter
			self.logger.debug(u'Saving new filter..')
			includeFilters = self.load(valuesDict.get(u'includeFilters', self.store(list())))
			#self.logger.debug(u'JSON: %s' % getJSON)
			#includeFilters = self.load(getJSON)
			
			currFilter = {}
			currFilter[u'name'] = valuesDict[u'includeFilterName']
			if self.ed: self.logger.debug(u'tmpDict: %s' % unicode(currFilter))

			includeFilters.append(currFilter)
			valuesDict[u'includeFilters'] = self.store(includeFilters)
			valuesDict[u'selectedIncludeFilter'] = unicode(len(includeFilters)-1)
			
		self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		return valuesDict
		

	########################################
	# UI VALIDATION
	########################################	
	
	# Validate plugin prefs changes:
	def validatePrefsConfigUi(self, valuesDict):
		self.logger.debug(u'CALL validatePrefsConfigUI, valuesDict: %s' % unicode(valuesDict))
		
		errorDict = indigo.Dict()
		'''if len(valuesDict[u'varFolderName']) == 0:
			errorDict[u'varFolderName'] = u'Please specify a name for the variable folder'
			errorDict[u'showAlertText'] = u'Please specify a name for the variable folder'
			
		if not valuesDict[u'debugLog']:
			valuesDict[u'extensiveDebug'] = False'''
			
		if len(errorDict) > 0:
			return (False, valuesDict, errorDict)
		else:
			return (True, valuesDict)
		
		
	# def getDeviceConfigUiValues():
	# possible to get values of device config UI?	
		
	# Catch changes to config prefs
	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		self.logger.debug(u'CALL closedPrefsConfigUi, valuesDict: %s' % unicode(valuesDict))
		self.logger.debug(u'CALL closedPrefsConfigUi, userCancelled: %s' % unicode(userCancelled))
		
		self.setUpdatePluginPrefs(True)
		
		# DO VALIDATION
		self.pluginConfigErrorState = False
		
	########################################
	# HELPERS
	########################################	
	

	########################################
	# Store and load information
	def store(self, val):
		return json.dumps(val)
	
	def load(self, val):
		return json.loads(val)
