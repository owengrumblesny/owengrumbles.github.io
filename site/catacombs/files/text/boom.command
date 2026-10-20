#!/bin/bash

while true; do
    open -a TextEdit
    osascript -e 'tell application "TextEdit" to make new document'
    sleep 1
done
