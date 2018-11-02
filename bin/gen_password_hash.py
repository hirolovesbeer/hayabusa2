#!/usr/bin/env python
import sys
import bcrypt

password = sys.argv[1]
salt = bcrypt.gensalt(rounds=10, prefix=b'2a')
hash = bcrypt.hashpw(password.encode('utf-8'), salt)
print(hash.decode('utf-8'))
