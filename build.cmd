copy ..\elzwelle_stopwatch.py .
copy ..\googlesheet.py .
mkdir dist
mkdir dist\elzwelle_stopwatch
\opt\miniconda3\Scripts\pyinstaller.exe elzwelle_stopwatch.py 
copy \opt\miniconda3\Library\bin\libcrypto-3-x64.dll 	dist\elzwelle_stopwatch\_internal
copy \opt\miniconda3\Library\bin\libssh2.dll 			dist\elzwelle_stopwatch\_internal
copy \opt\miniconda3\Library\bin\libssl-3-x64.dll		dist\elzwelle_stopwatch\_internal
