"""
SCons for Symbian - Preprocessor utility
"""

import os
import sys
from os.path import abspath
from SCons.Script import Command

CPP = os.environ["EPOCROOT"] + os.path.join( "epoc32", "gcc", "bin", "cpp" )

def Preprocess( env, target, source, includes, fileinc, defines ):
    """Utility for creating Command for preprocessor"""
    cmd=[
            CPP,
            "-undef -C -I-",
            "-I",
            " -I ".join( [ abspath(x) for x in includes ]  ), # Requires absolute path!

            " -D" + " -D".join( defines ),
            source,
            " -o %s" % target,
            " -include",
            " -include ".join( [ abspath(x) for x in fileinc ] ) # Requires absolute path!
        ]
    cmd = " ".join( cmd )
    
    return env.Command( target, source, cmd )



