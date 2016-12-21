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
		if self.ed: self.logger.debug(u'CALL getTriggerList')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		if self.ed: self.logger.debug(u'filter: %s' % filter)
		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
		if self.ed: self.logger.debug(u'targetId: %s' % targetId)
		
		if filter in [u'includeFilters', u'excludeFilters']:
			myArray = [
				(u"_blank",u" "),
				(u"_createNew",u"Create new filter...")]
		elif filter in [u'alarmTypes']:
			myArray = [
				(u"all",u"All")]
		elif filter in [u'eventsInclude', u'eventsExclude']:
			myArray = list()
			
		if filter == u'includeFilters' or filter == u'excludeFilters':
			if filter in valuesDict:
				if self.ed: self.logger.debug(u'%s: %s' % (unicode(filter), unicode(valuesDict[filter])))
				filterList = self.load(valuesDict.get(filter, self.store(list())))
				for filterNum, filterDict in enumerate(filterList):
					#self.logger.debug(u'k: %s, v: %s' % (k,v))
					myArray.append( (filterNum,filterDict['name']) )
		elif filter == u'alarmTypes':
			for cmdType, cmdTypeDict in self.zDefs[u'0x71'][u'types'].items():
				myArray.append( (cmdType,safeGet(cmdTypeDict, u'%s - Unspecified type' % unicode(cmdType), u'description')) ) 
		elif filter == u'eventsInclude' or filter == u'eventsExclude':
			if filter == u'eventsInclude': typeKey = u'includeFilterType'
			elif filter == u'eventsExclude': typeKey = u'excludeFilterType'
			
			if typeKey not in valuesDict:
				pass
			elif valuesDict[typeKey] == u'all':
				if self.ed: self.logger.debug(u'Selected all alarm types')
			elif not valuesDict[typeKey] in self.zDefs[u'0x71'][u'types']:
				pass
				#self.logger.warn(u'Invalid or no selected alarm/notification type')
			else:
				myArray = [(u"all",u"All")]
				for event, eventDict in self.zDefs[u'0x71'][u'types'][valuesDict[typeKey]][u'events'].items():
					myArray.append( (event,unicode(event) + u' - ' + safeGet(eventDict, u'Unspecified event', u'description')) )
					
		if self.ed: self.logger.debug(u'myArray: %s' % unicode(valuesDict))

		return myArray	
	
	def x71receivedIncludeFilterChangedFilterSelection(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterChanged(u'includeFilter', valuesDict, typeId, targetId)
		return valuesDict
	
	def x71receivedExcludeFilterChangedFilterSelection(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterChanged(u'excludeFilter', valuesDict, typeId, targetId)
		return valuesDict

	def selectedFilterChanged(self, type, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL selectedFilterChanged')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
		if self.ed: self.logger.debug(u'targetId: %s' % targetId)
		if self.ed: self.logger.debug(u'type: %s' % type)
		
		if type == u'includeFilter':
			typeC = u'IncludeFilter'
		elif type == u'excludeFilter':
			typeC = u'ExcludeFilter'
		else:
			self.logger.error(u'Unexpected filter type in selectedFilterChanged')
			return valuesDict

		# Clear all previous messages
		valuesDict[u'includeFilterStatus'] = ''
		valuesDict[u'showIncludeFilterStatus'] = False
		valuesDict[u'excludeFilterStatus'] = ''
		valuesDict[u'showExcludeFilterStatus'] = False

		if valuesDict[u'selected'+typeC] == u'_createNew' or valuesDict[u'selected'+typeC] == u'_blank':
			self.logger.debug(u'New filter selected, clearing values from UI')
			valuesDict[type+u'Name'] = u''
			valuesDict[type+u'Type'] = u''
			valuesDict[type+u'Events'] = list()
		else:
			self.logger.debug(u'Existing filter selected, retrieving stored values')
			if type+u's' in valuesDict:
				filterList = self.load(valuesDict.get(type+u's', self.store(list())))
				currFilter = filterList[int(valuesDict[u'selected'+typeC])]
				valuesDict[type+u'Name'] = currFilter[u'name']
				valuesDict[type+u'Type'] = currFilter[u'type']
				valuesDict[type+u'Events'] = currFilter[u'events']
				valuesDict[type+u'Status'] = ''
				valuesDict[u'show'+typeC+u'Status'] = False
				self.logger.debug(u'Retrieved selected filter "%s"' % (currFilter[u'name']))
			else:
				valuesDict[type+u'Status'] = 'Could not get selected filter'
				valuesDict[u'show'+typeC+u'Status'] = True
				self.logger.error(u'Could not get stored values for selected filter in selectedFilterChanged')
	
		if self.ed: self.logger.debug(u'return valuesDict: %s' % unicode(valuesDict))
		return valuesDict
		
		
	def x71receivedIncludeFilterChangedTypeSelection(self, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL x71receivedIncludeFilterChangedTypeSelection')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
		if self.ed: self.logger.debug(u'targetId: %s' % targetId)
		
		valuesDict[u'includeFilterEvents'] = list()
	
		return valuesDict
		
	def x71receivedExcludeFilterChangedTypeSelection(self, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL x71receivedExcludeFilterChangedTypeSelection')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
		if self.ed: self.logger.debug(u'targetId: %s' % targetId)
		
		valuesDict[u'excludeFilterEvents'] = list()
	
		return valuesDict
		
		
	# 	def selectedTriggerFilterChangedEventSelection(self, valuesDict=None, typeId="", targetId=0):
	# 		if self.ed: self.logger.debug(u'CALL selectedTriggerFilterChangedEventSelection')
	# 		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
	# 		if self.ed: self.logger.debug(u'typeId: %s' % typeId)
	# 		if self.ed: self.logger.debug(u'targetId: %s' % targetId)
	# 	
	# 		#self.logger.debug(u'return valuesDict: %s' % unicode(valuesDict))
	# 		return valuesDict

	def x71receivedSelectedIncludeFilterSave(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterSave(u'includeFilter', valuesDict, typeId, targetId)
		return valuesDict
		
	def x71receivedSelectedExcludeFilterSave(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterSave(u'excludeFilter', valuesDict, typeId, targetId)
		return valuesDict		
		
	def selectedFilterSave(self, type, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL selectedFilterSave')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		
		errorMsg = list()
		valError = False
		filterAction = ''
		
		if type == u'includeFilter':
			typeC = u'IncludeFilter'
		elif type == u'excludeFilter':
			typeC = u'ExcludeFilter'
		else:
			self.logger.error(u'Unexpected filter type in selectedFilterSave')
			return valuesDict

		if valuesDict[u'selected'+typeC] == u'_createNew': filterAction = 'new' # Saving new filter
		elif valuesDict[u'selected'+typeC] != u'_blank': filterAction = 'modify' #Modifying existing filter
		elif valuesDict[u'selected'+typeX] == u'_blank': filterAction = 'blank' #No filter selected
		
		if filterAction == 'new' or filterAction == 'modify':
			filterList = self.load(valuesDict.get(type+u's', self.store(list())))
			
			if filterAction == 'new':
				self.logger.debug(u'Saving new filter..')
				currFilter = {}
			elif filterAction == 'modify':
				self.logger.debug(u'Modifying existing filter..')
				currFilter = filterList[int(valuesDict[u'selected'+typeC])]
			
			# Filter name
			if len(valuesDict[type+u'Name']) > 0:
				currFilter[u'name'] = valuesDict[type+u'Name']
			else:
				errorMsg.append(u'Please specify a filter name')
				valError = True
			
			# Filter alarm types
			if not valuesDict[type+u'Type'] in self.zDefs[u'0x71'][u'types'] and valuesDict[type+u'Type'] != u'all':
				errorMsg.append(u'Invalid or no alarm/notification type selected')
				valError = True
			currFilter[u'type'] = valuesDict[type+u'Type']
			
			# Filter events
			if u'all' in valuesDict[type+u'Events']:
				currFilter[u'events'] = u'all'
			elif len(valuesDict[type+u'Events']) > 0:
				currFilter[u'events'] = list(valuesDict[type+u'Events']) # need to convert indigo list to python list, for json
			else:
				errorMsg.append(u'Invalid or no event selected')
				valError = True
			
			if self.ed: self.logger.debug(u'currFilter: %s' % unicode(currFilter))
			
			if valError:
				valuesDict[type+u'Status'] = '\n'.join(errorMsg)
				valuesDict[u'show'+typeC+u'Status'] = True
			else:
				try:
					if filterAction == 'new':
						filterList.append(currFilter)
						valuesDict[type+u's'] = self.store(filterList)
						valuesDict[u'selected'+typeC] = unicode(len(filterList)-1)
						valuesDict[type+u'Status'] = 'Saved'
						valuesDict[u'show'+typeC+u'Status'] = True
					elif filterAction == 'modify':
						valuesDict[type+u's'] = self.store(filterList)
						valuesDict[type+u'Status'] = 'Modified'
						valuesDict[u'show'+typeC+u'Status'] = True
				except:
					self.logger.exception(u'Could not save filter: %s' % (unicode(currFilter)))
					
		elif filterAction == 'blank':
			valuesDict[type+u'Status'] = 'Please select a filter before saving'
			valuesDict[u'show'+typeC+u'Status'] = True
			
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		return valuesDict
		
	def x71receivedSelectedIncludeFilterDelete(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterDelete(u'includeFilter', valuesDict, typeId, targetId)
		return valuesDict
		
	def x71receivedSelectedExcludeFilterDelete(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterDelete(u'excludeFilter', valuesDict, typeId, targetId)
		return valuesDict		
		
	def selectedFilterDelete(self, type, valuesDict=None, typeId="", targetId=0):
		if self.ed: self.logger.debug(u'CALL selectedFilterDelete')
		if self.ed: self.logger.debug(u'valuesDict: %s' % unicode(valuesDict))
		
		errorMsg = list()
		valError = False
		filterAction = ''
		
		if type == u'includeFilter':
			typeC = u'IncludeFilter'
		elif type == u'excludeFilter':
			typeC = u'ExcludeFilter'
		else:
			self.logger.error(u'Unexpected filter type in selectedFilterSave')
			return valuesDict
			
		filterList = self.load(valuesDict.get(type+u's', self.store(list())))
		
		try:
			deletedFilter = filterList.pop(int(valuesDict[u'selected'+typeC]))
			self.logger.debug(u'Deleted filter "%s"'  % (deletedFilter[u'name']))
			valuesDict[type+u's'] = self.store(filterList)
			valuesDict[type+u'Status'] = 'Filter "%s" deleted' % (deletedFilter[u'name'])
			valuesDict[u'show'+typeC+u'Status'] = True
			# Clear values from UI
			valuesDict[type+u'Name'] = ''
			valuesDict[type+u'Type'] = ''
			valuesDict[type+u'Events'] = list()
			valuesDict[u'selected'+typeC] = u'_blank'
		except:
			self.logger.exception(u'Could not delete filter')
			valuesDict[type+u'Status'] = 'Error: Could not delete filter'
			valuesDict[u'show'+typeC+u'Status'] = True
			
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
			
	def validateEventConfigUi(self, valuesDict=None, typeId='', eventId=0):
		# Do your validation logic here
		errorDict = indigo.Dict()
		# 		errorDict["someKey"] = "The value of this field must be from 1 to 10"
		# 		errorDict[“showAlertText”] = “Some very descriptive message to your user that will help them solve the validation problem.”
		
		# Make sure selected values are reset
		valuesDict[u'includeFilterStatus'] = ''
		valuesDict[u'showIncludeFilterStatus'] = False
		valuesDict[u'includeFilterName'] = ''
		valuesDict[u'includeFilterType'] = ''
		valuesDict[u'includeFilterEvents'] = list()
		valuesDict[u'selectedIncludeFilter'] = u'_blank'
		
		valuesDict[u'excludeFilterStatus'] = ''
		valuesDict[u'showExcludeFilterStatus'] = False
		valuesDict[u'excludeFilterName'] = ''
		valuesDict[u'excludeFilterType'] = ''
		valuesDict[u'excludeFilterEvents'] = list()
		valuesDict[u'selectedExcludeFilter'] = u'_blank'
		
		return (True, valuesDict, errorDict)
		
		
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
