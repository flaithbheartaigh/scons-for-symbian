"""
Console output colorizer. pyreadline required( on windows )
"""
__author__ = "Jussi Toivola"
__license__ = "MIT License"

from SCons.Platform import win32, posix
import os
import subprocess as sp
import sys


#: Pyreadline console
CONSOLE = None
try:
    if os.name == "nt":
        import pyreadline
        CONSOLE = pyreadline.GetOutputFile()
except ImportError: #IGNORE:W0704
    pass

#: Color constants. TODO: Get from user settings.
class Colors( object ):
    WARNING = 14
    ERROR = 12
    NORMAL = 7
    COMMENT = 10
    
if sys.platform == "linux2":
    Colors.WARNING = 33
    Colors.ERROR = 31
    Colors.NORMAL = 0
    Colors.COMMENT = 32
    
#: Get initial color of the console
if CONSOLE is not None:
    Colors.NORMAL = CONSOLE.attr


#: Lines containing these strings are drawn in Colors.ERROR color
KEYWORD_ERRORS = [ __x.lower() for __x in [ "error:", " error ", "failed", " undefined ", "does not match", "illegal",
               "was expected", "The process cannot access",
               "No such file or directory", "*** ", "cannot be opened",
               "Cannot convert", "needed by", "explicit dependency" ] ]
KEYWORD_ERRORS.sort()

#: Excluded errors
KEYWORD_ERRORS_EXCLUDE = [ "error.c", "error.cpp", "error.h"  ]

#: Drawn with Colors.COMMENT
KEYWORD_COMMENT = [ __x.lower() for __x in [ "scons:", "note:", "copy(", "install file"] ]

#: Excluded comments
KEYWORD_COMMENT_EXCLUDE = []

#: Warning keywords. Drawn with Colors.WARNING
KEYWORD_WARNINGS = ["warning ", "warning:"]

#: Excluded warnings
KEYWORD_WARNINGS_EXCLUDE = ["-warning"]

#: Map colors to keywords.
KEYWORDMAP = [ ( KEYWORD_WARNINGS, KEYWORD_WARNINGS_EXCLUDE, Colors.WARNING ),
               ( KEYWORD_ERRORS, KEYWORD_ERRORS_EXCLUDE, Colors.ERROR ),
               ( KEYWORD_COMMENT, KEYWORD_COMMENT_EXCLUDE, Colors.COMMENT ) ]

class LineCounts( object ):
    def __init__( self ):
        self.Errors = 0
        self.Warnings = 0
        self.Others = 0
        self.reset()

    def reset( self ):
        self.Errors = 0
        self.Warnings = 0
        self.Others = 0

LINECOUNTS = LineCounts()

#: Original sys.stdout
savedstdout = sys.stdout
savedstderr = sys.stderr

def subsitute_env_vars( line, env ):
    """ Substitutes environment variables in the command line.
    
    E.g. dir %EPOCROOT% -> dir T:\
    
    The command line does not seem to do this automatically when launched
    via subprocess.
    """
    for key, value in env.items():
        line = line.replace( "%%%s%%" % key, value )
    return line
    
def _handle_posix_write(line,color):
    msg = "%02i" % color
    savedstdout.write( "\x1b[%sm" % ( msg ) )
    savedstdout.write( line )
    
    # Reset
    msg = "%02i" % 0
    savedstdout.write( "\x1b[%sm" % ( msg ) )

def write( line, color ):
    """Write line with color"""
    global CONSOLE

    if os.name == "posix" and sys.__stdout__.isatty():        
        return _handle_posix_write( line, color )  
    
    elif CONSOLE is not None:
        try:
            CONSOLE.write_color( line, color )
            CONSOLE.write_color( "", CONSOLE.attr )
            return
        
        except TypeError:
            # Occurs at least when redirecting data to a file
            # So disable the color support
            CONSOLE = None
    
    if color in [ Colors.ERROR, Colors.WARNING ]:
        savedstderr.write( line )
    else:
        savedstdout.write( line )
        
def comment( line ):
    "Util for comments"
    write( line + "\n", Colors.COMMENT )
    
def error( line ):
    "Util for errors"
    write( line, Colors.ERROR )


class ConsoleBase( object ):
    """Base class for colored console output"""
    
    def __init__( self ):
        self.savedstdout = sys.stdout
        self.savedstderr = sys.stderr
        
    def flush( self ):
        self.savedstderr.flush()
        self.savedstdout.flush()

    def read( self ):
        """Read both stdout and stderr and output the data with colors"""
        block = None
        result = ""
                
        while block != "":
            block = self.savedstdout.read()
            self.write( block )
            result += block

            block = self.savedstderr.read()
            self.write( block )
            result += block
        
        return result

    def write( self, text ):
        """Colorize each line based on the keywords"""
        
        lines = text.split( "\n" )
        
        for i in xrange( len( lines ) ):
            
            line = lines[i]
            lowcase = line.lower()

            detected = False
            for kws, excludes, color in KEYWORDMAP:
                # Check keywords and exclusion keywords
                if  len( [x for x in kws if x in lowcase] ) > 0 \
                and len( [x for x in excludes if x in lowcase] ) == 0:
                    write( line, color )
                    detected = True
                    break

            # Draw in normal color then
            if not detected:
                write( line, Colors.NORMAL )

            if i < ( len( lines ) - 1 ):
                write( "\n", Colors.NORMAL )
class OutputConsole( ConsoleBase ):
    """Handles spawning external processes and colors the console output.
    """
    def __init__( self ):
        ConsoleBase.__init__( self )

        self.savedspawn = os.spawnve
        
        sys.stdout = self
        sys.stderr = self
        
        win32.spawn = self.spawn
        posix.spawnvpe_spawn = self.spawn
        
    def spawn( self, sh, escape, cmd, args, env ): #IGNORE:W0613
        """
        Replaces SCons.Platform.spawn to colorize output of
        external processes
        """
        #import pdb;pdb.set_trace()
        #.replace( '"', '' )
        #FIXME: the " must be removed but not those with \ before them.
        tmp = []
        for x in args:
            x = x.replace(r'\"', '\???') # lets hope nobody wants to use \???
            x = x.replace(r'"', '')
            x = x.replace(r'\???', '"')
            tmp.append( subsitute_env_vars( x, env ) )
        args = tmp

        startupinfo = None
        if os.name == "nt":
            # Long command support <= 32766 for Windows
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
        
        stdout = sp.PIPE
        #import pdb;pdb.set_trace()
        if ( os.name == "posix" and args[0] == "wine" ):
            stdout = None
            
        # We get unicode objects in the environment from somewhere, which makes
        # Popen unhappy. Force the environment to strings.
        # TODO(mika.raento): fix the source of the unicode.
        env = dict([ (k, str(v)) for (k, v) in env.iteritems() ])

        p = sp.Popen( args, bufsize = 1024,
                    stdout = stdout, stderr = sp.STDOUT,
                    startupinfo = startupinfo,
                    shell = False, env = env )
        result = None
        #import pdb;pdb.set_trace()
        if p.stdout is not None:
            while result is None:
                # This is slow on Linux with Wine!!
                line = p.stdout.read()
                self.write( line )
                result = p.poll()
            # Get the last lines            
            line = p.stdout.readline()
            self.write( line )
            
        else:
            result = p.wait()
            
        return result
        
del __x
