#!/usr/bin/env python
import sys

from hayabusa.monitor import NFSClientCheck

program_name = sys.argv[0]
check = NFSClientCheck(program_name)
check.main(sys.argv)
