
```
v2.2f
-----------------------
 July, 9. 2007     
-----------------------
- Login loop fixed.

v2.2e
-----------------------
 July, 8. 2007     
-----------------------
- Fixed "Says 'Fleet limit hit' but there are free slots" (issues 240, 244 and 248)
- Fixed "KeyError: 'Laboratorio di ricerca'" (issue 245)
- Ability to set maximum number of probes the bot can use for a planet.
- Added suport for brazilian OGame

v2.2d
-----------------------
 June, 23. 2007     
-----------------------
- Fixed AttributeError: 'NoneType' object has no attribute 'group'

v2.2c
-----------------------
 June, 22. 2007     
-----------------------
- Number of cargos sent should be accurate now.

v2.2b
-----------------------
 June, 17. 2007     
-----------------------
- Added turkish
- Support for admiral officer.
- Database is backed up and restored if neccesary.
- Anti detection fix.

v2.2a
-----------------------
 June, 14. 2007     
-----------------------
- Small corrections for dutch and portuguese translations.

v2.2
-----------------------
 June, 11. 2007     
-----------------------
** Too many changes to mention, some of them are: **
- Added random delays.
- Configurable deuterium source planet
- Espionage reports can be copied to clipboard by right-clicking.
- Added chinese, danish, russian and dutch languages.
- New plugin system.
- Harder to detect by game admins.
- A lot less espionages are neccesary, hence less overall activity.
- Before attacks only one probe is sent.
- Much faster inactive planets search.
- Reserved slots are no longer filled with senseless espionages.
- Attacks and espionages from planets with no probes or cargos are deactivated for a while.
- Rush mode at midnight (attack new inactive planets as they are found if they are very rentable).
- Attacks are paused before midnight, in order to free slots for rush mode.
- Daily inactives scan is now done ASAP each day.
- Any available cargo type is sent if the selected type of attacking fleet is not available.
- Source planet and last espionage time are now shown in the main window.
- Internal algorithms rewritten.
- Minor changes and fixes.
- New translation item added in language files.

v2.1.2c
-----------------------
 March, 12. 2007     
-----------------------
- Planets are spied oredered to simulate human behaviour
- Planets are ordered correctly by resources in the database tab.
- Server and universe shown in windows title.
- Fixed another WindowsError: [Error 13]

v2.1.2b
-----------------------
 March, 11. 2007     
-----------------------
- Fixed bug AttributeError: 'module' object has no attribute 'SpyReport'
- Fixed bug WindowsError: [Error 13] (...) files/botdata/gamedata.dat

v2.1.2
-----------------------
 March, 10. 2007     
-----------------------
- Selectable attack algorithm.
- Less memory used.
- Algorithm that selects how many probes are sent is smarter.
- Now nothing is never deleted from the database.
- Planets are shown ordered.
- Made possible translation to chinese and korean (further testing needed).
- Fixed bug in daily inactive scan which after a while resulted in message 
  "Fatal error found, terminating. There are no undefended planets in range."
- Fixed bug bot not attacking players with no alliance.
- Source code refactored and other minor fixes.

v2.1.1b
-----------------------
 March, 5. 2007     
-----------------------
- Fixed bug "AttributeError: 'list' object has no attribute 'split'"

v2.1.1
-----------------------
 March, 5. 2007     
-----------------------
- Added command-line option (-a) to autostart bot without clicking start.
- Replaced list of planets to avoid by list of players and alliances to avoid.
- Customizable rentability formula.
- Redesigned options dialog and added options to customize user-agent and 
  solar systems per galaxy in the server.
- Fixed bug "ValueError: list.remove(x): x not in list"

v2.1k
-----------------------
 March, 2. 2007     
-----------------------
- Fixed "Connecting..." loop in Windows versions.

v2.1i
-----------------------
 March, 2. 2007     
-----------------------
- botdata now is backed up before re-spying.
- Added support for ogame.com.pt/ogame.com.br and ogame.com.hr/ogame.ba

v2.1e
-----------------------
 February, 28. 2007     
-----------------------
- Added some changes to emulate human behavior.
- Made possible translation to yugoslavian and portuguese.
- Added support for universes with more than 9 galaxies.
- Configurable number of solar systems per galaxy (see FAQ).
- Configurable user agent (see FAQ).
- Added support for proxy.

v2.1c
-----------------------
 February, 26. 2007     
-----------------------
- Fixed french translation

v2.1b
-----------------------
 February, 25. 2007     
-----------------------
- Fixed list of planets to avoid not working properly

v2.1
-----------------------
 February, 25. 2007     
-----------------------
- Added support for french (ogame.fr) and polish (ogame.pl)
- Added tolerance to buggy almost empty (N;) espionage reports.
- Added a configurable list of planets to avoid.
- Changed user agent to that of a fresh WinXP install: 
	Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)
- Removed range limit.
- Language files are no longer codified in UTF-8
- More descriptive messages when using translation files with errors.
- Other fixes.

v2.09
-----------------------
 February, 19. 2007     
-----------------------
- Added support for ogame.de
- Bot should work for both OGame 0.76 and 0.75

v2.08b
-----------------------
 February, 19. 2007     
-----------------------
- Now works with OGame last version, v0.76
- Added small delay after each espionage to simulate human behaviour.
- Fixed rare ImportError: No module named copy_reg

v2.07
-----------------------
 February, 14. 2007     
-----------------------
- Fixed bot only attacking with small cargos.
- Added fleet slots reservation for manual playing.
- Corrected spanish, english and italian translations.
- Improved hints for translations in the file english.ini
- Some minor changes.

v2.05b
-----------------------
 February, 6. 2007     
-----------------------
- Espionages are not sent if there are not enough probes available.

v2.05
-----------------------
 February, 5. 2007     
-----------------------
- Espionage data is reset if username, universe or webpage are changed.
- Daily inactives update happens at midnight not 8am, so changed that.


v2.04
-----------------------
 February, 5. 2007     
-----------------------
- Fixed bot never attacking because local date was different than server date.
- Translations do not have to match case.
- Logging works (log stored in files/log)
- Daily inactive scan is made at 8:10h, right after server update.
- All planets dont have to be spied again after changing attack radio or source planets.

v2.0
-----------------------
 February, 3. 2007     
-----------------------
- Now which planet will be attacked next is determined by a resource simulator that sorts target planets by quantity of potentially produced resources since last attack, and also taking distance into account.
- Possibility to choose which planet or planets are source of attacks. Moons are also allowed.
- Multi-language support. By now Spanish, English and Italian are included with the bot. To add one language just put the .ini file in the languages directory. Non-occidental languages should work also.
- Command line switch to have different configuration sets at once (example: --workdir uni18).
- Increases number of sent espionage probes until defense or buildings information is achieved.
- Redesigned user interface.


v1.0
-----------------------
 August, 23. 2006     
-----------------------
- First release
- Features: automated spy-and-attack to neighbour inactive planets with no defenses nor fleet
- Planet database



```