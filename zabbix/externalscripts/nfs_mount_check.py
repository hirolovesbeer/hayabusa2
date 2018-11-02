#!/usr/bin/env python
import sys

from hayabusa.monitor import MountCheck

program_name = sys.argv[0]
check = MountCheck(program_name)
check.main(sys.argv)
