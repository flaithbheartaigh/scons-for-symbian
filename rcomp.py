"""SCons for Symbian - RComp utility"""

import os
import sys
import cpp

from SCons.Script import Command

RCOMP = os.environ["EPOCROOT"] + os.path.join( "epoc32", "tools", "rcomp" )

def RComp( env, rsc, rsg, rss, options, includes, fileinc, defines ):
    """Utility for creating Command for Symbian resource compiler"""
    # Preprocess the resource file first
    rpp = ".".join( os.path.basename( rss ).split(".")[:-1] + ["rpp"] )
    rpp = os.path.join( os.path.dirname( rsg ), rpp )
    
    cpp.Preprocess( env, rpp, rss, includes, fileinc, defines + ["_UNICODE" ] )
    
    #def RunRComp( env, target = None, source = None ):
    cmd = RCOMP + ' -u %s -o"%s" -h"%s" -s"%s" -i"%s" ' % \
            ( options, rsc, rsg, rpp, rss )        
            
    return env.Command( [rsc,rsg], [rpp,rss], cmd )


