### Q: How do I run the bot in Windows? ###

A: After downloading the file, decompress it and run OGBot.exe

### Q: How do I run the bot in Linux? ###

A: Download the source version. Under Linux, the libraries required by the bot are usually provided by the distributions in form of packages, so getting it to work is pretty straightforward. For example, under Ubuntu the following packages are required:
  1. **python-qt4** for PyQt.
  1. **libqt4-core** and **libqt4-gui** for QT.
  1. **python2.4** for Python.
In other distros their names might differ but not much.
After installing them just run runbot.sh

bsddb is also required, and some distros don't provide it by default.
Note for Gentoo Linux: [PyQt4](http://packages.gentoo.org/search/?sstring=PyQt4) package is masked, so it can not to be installed by default. To do so, it has to be unmasked. Instructions [here](http://gentoo-wiki.com/TIP_Dealing_with_masked_packages).

### Q: I have Commander mode. Will the bot still work? ###

A: Yes. But you have to disable message grouping in folders in OGame options.


### Q: I have Officers. Will the bot still work? ###

A: Yes.


### Q: I found some error in the bot, how do I report it? ###

A: Go to the [issues tab](http://code.google.com/p/kovans-ogbot/issues/list) and see if someone has already reported it. If so, you can click the star near it to be notified of changes and comments. If not, open a new issue and then follow the instructions.  DO NOT post feature request here. Instead see next question:

### Q: I have a feature request, could you implement it? ###

A: You can comment it in the appropiate forum section. The author is a busy person though and only a few of them will likely be implemented.



### Q: How do I reset the bot? ###

A: Delete the files in the directory files/botdata.

### Q: When my IP changes I get "Fatal error found, terminating. (...) Your session is not valid. ###

A: Deactivate IP check in OGame options.

### Q: I get "Not enought technologies researched to run the bot". What do I need to research? ###

A: Currently the bot requires Combustion drive level 1 and Impulse drive level 1 to run.


### Q: Will I get banned if I use this bot? ###

A: Maybe. OGame admins are always finding new ways to detect it.
If you want to minimize the probabilities of getting baned follow these advices:
  * If you post in the issues tab or in the forums, do not use the same nick/e-mail as in the game (this one is important).
  * Do not leave the bot running day and night.

Probabilities of getting banned greatly depend on how much effort put GAs (AFAIK GOs can't detect the bot) in finding people that uses the bot. In some universes people are running the bot day and night for months without being banned. On the other hand, in some polish universes people are getting banned just because they have a lot of activity, without having any real proof of bot usage. In the latter cases promising you don't use any bot and all that activity is just because you play a lot might get you unbanned.


### Q: I've heard this bot has a virus. Is it true? ###

A: No. Someone uploaded a modified version of the bot in the forums, which had a virus or trojan. However the official version never had nor will have any. That's why the bot should always be downloaded only from this page.

### Q: Can I choose which browser does the "Launch web browser" button use? ###

A: You have to set the BROWSER environment variable to the command of the browser you want to use. A list of possible values and further instructions can be found here: http://docs.python.org/lib/module-webbrowser.html


### Q: How can I choose the language? ###

A: You can't. A common confusion is that language files also translate the bot messages. This is not true. Bot messages and user interface are always in English. Language files are only to support different countries' OGames. The correct language file will automatically be selected after the bot connects to the server and detects its language.

### Q: My language is not supported. Can I contribute a translation? ###

A: Sure. What you have to do is create a new translation file for your language and place it in the languages directory. You should use english.ini as a template, as there are further instructions in it. If it works send it to the author and it will probably be included in the next release. Not all languages are guaranteed to work thought.

### Q: How do I run the multi-platform (source) version of the bot in Windows? ###

A: The easiest and recommended way to run the bot in Windows is to use the prepared version, but it is possible to use the source version. These are the steps:

  1. Download & install Python 2.5 (http://www.python.org)
  1. Download & install QT 4 GPL for Windows (http://www.trolltech.com)
  1. Download & install PyQt v4 GPL for Windows (http://www.riverbankcomputing.co.uk)
  1. Add the QT bin directory and the Python directory to the PATH.

After all that, execute runbot.bat and it _should_ work.


### Q: Are there any 'hidden' configuration options? ###

A: There are some command-line options:

```

Usage: runbot.sh [options]

Options:
  -h, --help            show this help message and exit
  -c, --console         Run in console mode'
  -a, --autostart       Auto start bot, no need to click Start button
  -w WORKDIR, --workdir=WORKDIR
                        Specify working directory (useful to run various bots
                        at once). If not specified defaults to 'files'
  -p PLUGIN, --plugin=PLUGIN
                        Run the specified plugin from the plugins folder, and
                        exit. Example: to run plugins/auto.py: runbot.sh -p auto


```

### Q: How does the bot choose which planet to attack? ###

A: It assigns a rentability (a number) to each planet and always attacks that with the most rentability. Since v2.1.2, the planet selection algorithm can be chosen in Advanced Options.


Here is an extract from one issue's comments that explains the differences in the algorithms between OGBot versions 1 and 2.

_The_ _v2_ _algorithm_ _is_ _indeed_ _completly_
_different_ _from_ _that_ _of_ _v1._ _v1's_ _algorithm_ _consisted_ _simply_ _in:_
  1. _-_ _Scan_ _a_ _solar_ _system_ _for_ _inactives_
  1. _-_ _Spy_ _them_
  1. _-_ _Attack_ _those_ _that_ _had_ _more_ _resources_ _than_ _the_ _limit_ _the_ _user_ _configured._
  1. _-_ _Go_ _to_ _the_ _next_ _solar_ _system._

_V2's_ _algorithm,_ _on_ _the_ _other_ _hand,_ _is_ _completly_ _different._ _It_ _is_ _designed_ _to_ _collect_
_the_ _maximum_ _possible_ _resources_ _per_ _hour_ _by_ _both_ _minimizing_ _the_ _amount_ _of_ _neccesary_
_espionages_ _and_ _by_ _always_ _attacking_ _at_ _the_ _most_ _rentable_ _planet,_ _understanding_ _that_ _as_
_the_ _attack_ _that_ _most_ _resources_ _is_ _going_ _to_ _provide_ _the_ _player_ _by_ _unit_ _of_ _travel_ _time._
_The_ _algorithm_ _is_ _based_ _on_ _two_ _ideas:_

_-_ _The_ _mines_ _of_ _an_ _inactive_ _planet_ _are_ _never_ _going_ _to_ _change_ _troughout_ _the_ _time_ _it_
_remains_ _inactive._ _This_ _way,_ _the_ _planet_ _can_ _be_ _spied_ _only_ _once_ _to_ _determine_ _it's_ _mine_
_levels,_ _and_ _simulate_ _the_ _produced_ _resources_ _from_ _that_ _without_ _the_ _need_ _of_ _additional_
_espionages._ _In_ _case_ _it_ _gets_ _to_ _be_ _the_ _most_ _rentable_ _planet_ _to_ _attack,_ _it_ _will_ _be_
_spied_ _again_ _to_ _assure_ _it_ _has_ _not_ _been_ _attacked_ _by_ _other_ _player_ _in_ _the_ _meantime._

_-_ _Second_ _and_ _most_ _important:_ _you_ _get_ _the_ _same_ _amount_ _of_ _resources_ _by_ _attacking_ _a_ _far_
_planet_ _with_ _flight_ _time_ _of_ _2_ _hours_ _and_ _lots_ _of_ _resources,_ _than_ _by_ _attacking_ _two_ _near_
_planets_ _with_ _half_ _of_ _the_ _resources_ _each,_ _but_ _at_ _a_ _flight_ _time_ _of_ _1_ _hour._

_Additionally,_ _those_ _planets_ _with_ _fleet_ _or_ _defenses_ _are_ _re-spied_ _every_ _two_ _days,_ _just_
_in_ _case_ _they_ _have_ _been_ _destroyed,_ _and_ _every_ _night_ _the_ _list_ _of_ _inactive_ _planets_ _is_
_updated,_ _and_ _the_ _new_ _ones_ _are_ _spied._