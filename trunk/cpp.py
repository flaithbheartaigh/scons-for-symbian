"""Preprocessor utility"""



import os
import sys
from os.path import abspath
from SCons.Script import Command

#CPP = "cpp"#"arm-none-symbianelf-cpp"
CPP = os.environ["EPOCROOT"] + os.path.join( "epoc32", "gcc", "bin", "cpp" )

def Preprocess( env, target, source, includes, fileinc, defines ):

    cmd=[
            CPP,
            "-undef -C -I-",
            "-I",
            " -I ".join( [ abspath(x) for x in includes ]  ),

            " -D" + " -D".join( defines ),
            source,
            " -o %s" % target,
            " -include",
            " -include ".join( [ abspath(x) for x in fileinc ] )
        ]
    cmd = " ".join( cmd )
    print cmd
    return env.Command( target, source, cmd )



