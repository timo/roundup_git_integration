#!/bin/sh
ROUNDUP_BASE='http://example.com/roundup/'
perl -pe 's{(issue(\d+))}{<a href="$ENV{ROUNDUP_BASE}/issue$2">$1</a>}ig'
