# ZEAL - Z-Wave Event and Alarm Listener - Indigo plugin

This [Indigo](http://www.indigodomo.com) plugin allows you to listen for and create triggers for most known z-wave notification reports. The plugin is currently configured for 195 different reports. A Z-wave notification report can be low battery, door opened, fire alarm triggered, device overload etc. 
The plugin also allows you to create very flexible triggers for z-wave device battery levels and reports. 
Furthermore, it keeps track of outgoing z-wave commands and you can create triggers for failed commands or slow commands.
It also keeps statistics on your Z-wave network, you will be able to see how many ingoing and outgoing commands of each type to/from each device, as well as minimum, maximum and average response time.

## Main features

* Triggers on Z-wave notification reports
* Triggers on Z-wave battery reports
* Triggers on failed or slow outgoing Z-wave commands
* Z-wave network statistics
* Very flexible trigger configuration, allows you to use a "filter" style meaning you can create a single trigger for all your devices. It is also possible to exclude devices, meaning you can create a trigger for "all but one" devices. If you then add a new Z-wave device to your network, it is automatically included in your existing trigger.
* The filter style trigger also allows you to select multiple notification reports for the same trigger. This means you for example can create a single trigger for all your door sensors, which triggers both when the door opens and closes.
* The battery triggers can be configured to reset in a number of different ways. Meaning you can choose to have it trigger only once when the battery drops below a certain level. Or it can trigger every X hours. Trigger can be automatically re-enabled when battery is replaced.
* Since the plugin supports making single triggers for multiple devices, it can be configured to save triggering device information to variables, so that this information can be used in actions.
* Table with Z-Wave statistics can be output to Indigo log or sent via e-mail. It is recommended to use the Better E-mail plugin for this, to allow formatted HTML e-mail.

## Documentation

Documentation is in progress and will be added to the [Wiki](https://github.com/kris10an/ZEAL/wiki), meanwhile usage information can be found in this [forum thread](http://forums.indigodomo.com/viewtopic.php?f=261&t=17738)
