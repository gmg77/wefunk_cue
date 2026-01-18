# wefunk-cue-grabber
Update of our funky friend elohmeier python script to create cue sheets from shows of WEFUNK RADIO

## Changes
-fixed some issues with date and filenaming
-command line simplified for range of shows

## Dependencies
- python-lxml
- mp3 files from wefunk.com optional but highly recommended

## Quick Start
-pip install lxml
-python wefunkcue.py
  Simple Mode (Single Show): python wefunkcue.py 1234
  Range Mode (Multiple Shows): python wefunkcue.py --start 1230 --end 1234
  If you run it without arguments, it will ask for input interactively!


## USAGE
Cue file for single show mp3
Cue files can be processed in superior players like (https://www.foobar2000.org)

or split with mp3splt
```
for f in $(find -name "*.mp3")
do
mp3splt -o "@b/@N - @p - @t" -c $(basename $f .mp3).cue $f
done
```
