"""
SCons for Symbian - SCons build toolchain support for Symbian
"""
__author__    = "Jussi Toivola"
__license__   = "MIT License"

import os
import textwrap

from SCons.Environment import Environment
from SCons.Builder     import Builder
from SCons.Options     import Options, EnumOption
from SCons.Script      import ARGUMENTS, Command, Copy, Execute, Depends, BuildDir


#: Easy constant for free caps
FREE_CAPS = "NetworkServices LocalServices ReadUserData WriteUserData Location UserEnvironment PowerMgmt ProtServ SwEvent SurroundingsDD ReadDeviceData WriteDeviceData TrustedUI".split()


#: Symbian SDK folder
EPOCROOT = os.environ["EPOCROOT"]


_p = os.environ["PATH"]
#: Path to arm toolchain. Detected automatically from path using 'CSL Arm Toolchain'
PATH_ARM_TOOLCHAIN = [ _x for _x in _p.split(";") if "CSL Arm Toolchain\\bin" in _x ][0]

#: Remove drive name from EPOCROOT
#: Some Symbian tools requires this. TODO: Rewrite 'em and get rid of this thing!    
if ":" in EPOCROOT: 
    EPOCROOT = EPOCROOT.split(":",1)[-1]
    
print "EPOCROOT=%s" % EPOCROOT
os.environ["EPOCROOT"] = EPOCROOT

COMPILER_WINSCW = "WINSCW"
COMPILER_GCCE   = "GCCE"
RELEASE_UREL    = "UREL"
RELEASE_UDEB    = "UDEB"

TARGETTYPE_DLL    = "DLL"
TARGETTYPE_PYD    = "PYD"
TARGETTYPE_EXE    = "EXE"
TARGETTYPE_PLUGIN = "PLUGIN"

#: List of possible targettypes
TARGETTYPES       = [ TARGETTYPE_DLL,
                      TARGETTYPE_EXE,
                      TARGETTYPE_PYD,
                      TARGETTYPE_PLUGIN ]

#: Types, which are actually just dlls
DLL_TARGETTYPES = [ TARGETTYPE_DLL, TARGETTYPE_PYD ]

#: Maps targettype to correct uid
TARGETTYPE_UID_MAP = {
    TARGETTYPE_DLL : "0x10000079",
    TARGETTYPE_EXE : "0x1000007a"
}

opt = Options(None, ARGUMENTS)
opt.AddOptions(
         EnumOption(
          'compiler',
          'The compiler you want to use',
          'winscw',
          ['gcce','gcce'],
          {'winscw':'winscw'}))

#: Used compiler
COMPILER   = ARGUMENTS.get( "compiler", COMPILER_WINSCW ).upper()

#: Urel/Udeb
RELEASE    = ARGUMENTS.get( "release",  RELEASE_UDEB ).upper()

#: Built components. One SConstruct can define multiple SymbianPrograms.
#: This can be used from command-line to build only certain SymbianPrograms
COMPONENTS = ARGUMENTS.get( "components",  None )
if COMPONENTS is not None:
    COMPONENTS = COMPONENTS.upper().split(",")

def __get_defines():
    "Ensure correct syntax for defined strings"
    tmp = ARGUMENTS.get( "defines",  None )
    if tmp is None: return []
    tmp = tmp.split(",")

    defs = []
    for x in tmp:
        if "=" in x:
            name, value = x.split("=")
            if not value.isdigit():
                value = r'\"' + value + r'\"'

            x = "=".join( [name, value] )

        defs.append(x)
    return defs

#: Command-line define support
CMD_LINE_DEFINES = __get_defines()


# TODO: freeze # perl -S \epoc32\tools\efreeze.pl %(FROZEN)s %(LIB_DEFS)s
print "Building", COMPILER, RELEASE
print "Defines", CMD_LINE_DEFINES

#: UID.cpp for WINSCW simulator
TARGET_UID_CPP_TEMPLATE_DLL = r"""
// scons-generated uid source file
#include <e32cmn.h>
#pragma data_seg(".SYMBIAN")
__EMULATOR_IMAGE_HEADER2(0x10000079,0x00000000,0x00000000,EPriorityForeground,0x000ff1b4u,0x00000000u,0x00000000,0,0x00010000,0)
#pragma data_seg()
"""
#: UID.cpp for WINSCW simulator
TARGET_UID_CPP_TEMPLATE_EXE = r"""
// scons-generated uid source file
#include <e32cmn.h>
#pragma data_seg(".SYMBIAN")
__EMULATOR_IMAGE_HEADER2(0x1000007a,0x100039ce,%(UID3)s,EPriorityForeground,0x000ff1b4u,0x00000000u,%(UID3)s,0x00000000,0x00010000,0)
#pragma data_seg()
"""

# in template
# UID2 = 0x100039ce for exe
# UID2 = 0x00000000 for dll

# More defines set by getenvironment
DEFAULT_SYMBIAN_DEFINES = [ "__SYMBIAN32__",
                            "_UNICODE",
                            "__SERIES60_30__",
                            "__SERIES60_3X__",
                            #"__S60__",
                            "__SUPPORT_CPP_EXCEPTIONS__",
                             ]

if RELEASE == RELEASE_UREL:
    DEFAULT_SYMBIAN_DEFINES.append( "NDEBUG" )
else:
    DEFAULT_SYMBIAN_DEFINES.append( "_DEBUG" )


DEFAULT_GCCE_DEFINES = DEFAULT_SYMBIAN_DEFINES[:]
DEFAULT_GCCE_DEFINES += [
                        "__GCCE__",
                        "__EPOC32__",
                        "__MARM__",
                        "__EABI__",                        
                        "__MARM_ARMV5__",
                        ("__PRODUCT_INCLUDE__", '"' + os.path.normpath( EPOCROOT + r'Epoc32/include/variant/Symbian_OS_v9.1.hrh') + '"' )
                        ]

DEFAULT_WINSCW_DEFINES = DEFAULT_SYMBIAN_DEFINES[:]
DEFAULT_WINSCW_DEFINES += [
                        "__CW32__",
                        "__WINS__",
                        "__WINSCW__"
                        ]

INCLUDES = [ EPOCROOT +'Epoc32/include',
             EPOCROOT + r"Epoc32\include\variant",
             #r'D:\Symbian\CSL Arm Toolchain\bin\..\lib\gcc\arm-none-symbianelf\3.4.3\include'
           ]
SYMBIAN_ARMV5_LIBPATHDSO = EPOCROOT + r"Epoc32\RELEASE\ARMV5\LIB\\"
SYMBIAN_ARMV5_LIBPATHLIB = EPOCROOT + r"Epoc32\RELEASE\ARMV5\UREL\\"
SYMBIAN_WINSCW_LIBPATHLIB = EPOCROOT + r"Epoc32\RELEASE\WINSCW\UDEB\\"

#SYMBIAN_ARMV5_BASE_LIBRARIES = [ "drtrvct2_2", "scppnwdl", "drtaeabi", "dfprvct2_2", "dfpaeabi", "usrt2_2" ]
SYMBIAN_ARMV5_BASE_LIBRARIES =  [ SYMBIAN_ARMV5_LIBPATHLIB + x + ".lib" for x in [ "usrt2_2" ] ]
SYMBIAN_ARMV5_BASE_LIBRARIES += [ SYMBIAN_ARMV5_LIBPATHDSO + x + ".dso" for x in "drtrvct2_2", "scppnwdl", "drtaeabi", "dfprvct2_2", "dfpaeabi" ]


# LIBARGS must be AFTER the libraries or we get "undefined reference to `__gxx_personality_v0'" when linking

WARNINGS =  "-Wall -Wno-ctor-dtor-privacy -Wno-unknown-pragmas -fexceptions " \
            "-march=armv5t -mapcs -pipe -nostdinc -msoft-float"


def get_output_folder(compiler, release, target, targettype ):
    return "%s_%s\\%s_%s" % (compiler, release, target, targettype )

def getenvironment( *args, **kwargs ):
    env = None
    if COMPILER == COMPILER_GCCE:
        env = get_gcce_compiler_environment( *args, **kwargs )
    else:
        env = get_winscw_compiler_environment( *args, **kwargs )
    return env

def get_winscw_compiler_environment(  target,
                                    targettype,
                                    includes,
                                    libraries,
                                    uid2,
                                    uid3,
                                    definput = None,
                                    capabilities = None,
                                    defines = None ):

    OUTPUT_FOLDER = get_output_folder( COMPILER, RELEASE, target, targettype )

    LIBPATH   = SYMBIAN_WINSCW_LIBPATHLIB
    LIBRARIES = [ os.path.normpath(LIBPATH + x ).upper() for x in libraries ]

    if defines is None:
        defines = []
    defines.extend( DEFAULT_WINSCW_DEFINES )
    defines.extend( CMD_LINE_DEFINES )

    if targettype in DLL_TARGETTYPES:
        defines.append( "__DLL__" )
    else:
        defines.append( "__EXE__" )
    defines = [ '"%s"' % x for x in defines ]

    WINSCW_CC_FLAGS = '-g -O0 -inline off -wchar_t off -align 4 -warnings on -w nohidevirtual,nounusedexpr -msgstyle gcc -enum int -str pool -exc ms -trigraphs on  -nostdinc'
     #%(EPOCROOT)sEPOC32\RELEASE\WINSCW\UDEB\euser.lib %(EPOCROOT)sEPOC32\RELEASE\WINSCW\UDEB\efsrv.lib
    LINKFLAGS = ""
    if targettype in DLL_TARGETTYPES:
        LINKFLAGS     = """
                    -msgstyle gcc
                    -stdlib "%(EPOCROOT)sEPOC32\RELEASE\WINSCW\UDEB\EDLL.LIB"
                    -noentry -shared
                    -subsystem windows
                    -g
                    -export dllexport
                    -m __E32Dll
                    -nocompactimportlib
                    -implib %(OUTPUT_FOLDER)s\\%(TARGET)s._tmp_lib
                    -addcommand "out:%(TARGET)s._tmp_%(TARGETTYPE)s"
                    -warnings off
                     """

    elif targettype == TARGETTYPE_EXE:
        LINKFLAGS     = """
                    -msgstyle gcc
                    -stdlib "%(EPOCROOT)sEPOC32\RELEASE\WINSCW\UDEB\EEXE.LIB"
                    -m "?_E32Bootstrap@@YGXXZ"
                    -subsystem windows -g
                    -noimplib
                     """

    #-search LogMan.o LogMan_UID_.o
    #-o "%(TARGET)s.%(TARGETTYPE)s"
    #import textwrap
    LINKFLAGS = textwrap.dedent( LINKFLAGS )
    LINKFLAGS = " ".join( [ x.strip() for x in LINKFLAGS.split("\n") ] )

    LINKFLAGS = LINKFLAGS % {"TARGET"     : target,
                             "TARGETTYPE" : targettype,
                             "EPOCROOT"   : EPOCROOT,
                             "COMPILER"   : COMPILER,
                             "OUTPUT_FOLDER": OUTPUT_FOLDER }


    COMPILER_INCLUDE = os.path.normpath( EPOCROOT + "/Epoc32/INCLUDE/GCCE/GCCE.h" )
    env = Environment( ENV = os.environ,#os.environ['PATH'],
                   CXX = r'mwccsym2.exe',
                   #CCCOMFLAGS= '$CPPFLAGS $_CPPDEFFLAGS $_CPPINCFLAGS -o $TARGET $SOURCES',
                   #CCFLAGS = WINSCW_CC_FLAGS,#'-O2',
                   CPPPATH = INCLUDES + includes,
                   CPPDEFINES = defines,
                   CXXFLAGS   = WINSCW_CC_FLAGS + ' -cwd source -i- -include "Symbian_OS_v9.1.hrh"', #WARNINGS + " -x c++ -include " + COMPILER_INCLUDE,
                   INCPREFIX  = "-i ",
                   CPPDEFPREFIX = "-d ",
                   # Linker settings
                    LINK    = r'mwldsym2.exe',
#                     LIBPATH = [
#                                  r"D:\Symbian\CSL Arm Toolchain\lib\gcc\arm-none-symbianelf\3.4.3",
#                                  r"D:\Symbian\CSL Arm Toolchain\arm-none-symbianelf\lib"
#                               ],
                    LINKFLAGS     = LINKFLAGS,
                    LIBS          = LIBRARIES,
                    LIBLINKPREFIX = " ",
                    PROGSUFFIX    = "." + targettype

                )

    return env

def get_gcce_compiler_environment(  target,
                                    targettype,
                                    includes,
                                    libraries,
                                    uid2,
                                    uid3,
                                    definput = None,
                                    capabilities = None,
                                    defines = None ):
    """Create GCCE building environment
    """

    if defines is None:
        defines = []
    
    if targettype in DLL_TARGETTYPES:
        defines.append( "__DLL__" )
    else:
        defines.append( "__EXE__" )
        
    defines.extend( DEFAULT_GCCE_DEFINES )
    defines.extend( CMD_LINE_DEFINES )
    

    LIBARGS   = [ "-lsupc++", "-lgcc" ]
    LIBPATH   = SYMBIAN_ARMV5_LIBPATHDSO
    
    # GCCE uses .dso instead of .lib
    LIBRARIES = [ LIBPATH + x.lower().replace(".lib", ".dso") for x in libraries ]#+ ".dso"    
    if targettype == TARGETTYPE_EXE:
        LIBRARIES.append( r"\EPOC32\RELEASE\ARMV5\LIB\eikcore.dso" )
    
    LIBRARIES = LIBRARIES + SYMBIAN_ARMV5_BASE_LIBRARIES
    LIBRARIES.sort()
    LIBRARIES += LIBARGS 
    # Cleanup
    LIBRARIES = [ x.replace( "\\\\", "\\") for x in LIBRARIES ]
    
    #import pdb;pdb.set_trace()
    COMPILER_INCLUDE = os.path.abspath( EPOCROOT + "Epoc32\\INCLUDE\\GCCE\\GCCE.h" )
        
    # Create linker flags
    LINKFLAGS     = r"""
                    --target1-abs --no-undefined -nostdlib
                    -shared -Ttext 0x8000 -Tdata 0x400000
                    --default-symver
                    -soname %(TARGET)s{%(UID2)s}[%(UID3)s].exe
                    --entry _E32Startup  -u _E32Startup
                    %(EPOCROOT)sEpoc32\RELEASE\ARMV5\UREL\EDLL.LIB
                    -Map %(EPOCROOT)sEpoc32\RELEASE\GCCE\UREL\%(TARGET)s.%(TARGETTYPE)s.map
                    """
    if targettype == TARGETTYPE_EXE:
        LINKFLAGS = LINKFLAGS.replace( "EDLL.LIB", "EEXE.LIB" )
         
    LINKFLAGS = textwrap.dedent( LINKFLAGS )
    LINKFLAGS = " ".join( [ x.strip() for x in LINKFLAGS.split("\n") ] )

    LINKFLAGS = LINKFLAGS % {"UID2"   : uid2,
                             "UID3"   : uid3,
                             "TARGET" : target,
                             "TARGETTYPE"   : targettype,
                             "EPOCROOT" : EPOCROOT }
    

    ELF2E32 =   r"""
                %(EPOCROOT)sEpoc32\Tools\elf2e32 --sid=%(UID3)s
                --uid1=%(UID1)s --uid2=%(UID2)s --uid3=%(UID3)s
                --vid=0x00000000
                --capability=%(CAPABILITIES)s
                --fpu=softvfp --targettype=%(TARGETTYPE)s
                --output=$TARGET
                %(DEFCONFIG)s
                --elfinput="%(WORKING_DIR)s\$SOURCE"
                --linkas=%(TARGET)s{000a0000}[%(UID3)s].%(TARGETTYPE)s
                --libpath="%(EPOCROOT)sEPOC32\RELEASE\ARMV5\LIB"
                """
    #--output="%(EPOCROOT)sEPOC32\RELEASE\GCCE\%(RELEASE)s\$TARGET"
    #import textwrap
    ELF2E32 = textwrap.dedent( ELF2E32 )
    ELF2E32 = " ".join( [ x.strip() for x in ELF2E32.split("\n") ] )

    defconfig = ""
    # Based on targettype
    #uid1 = "0x1000007a" # Exe
    uid1 = ""
    elf_targettype = ""
    if targettype in DLL_TARGETTYPES:
        uid1 = TARGETTYPE_UID_MAP[TARGETTYPE_DLL]
        elf_targettype = TARGETTYPE_DLL
    else:
        uid1 = TARGETTYPE_UID_MAP[targettype]
        elf_targettype = TARGETTYPE_EXE

    if targettype in DLL_TARGETTYPES:

        defconfig = []
        if definput is not None:
            definput = os.path.abspath( definput )
            defconfig +=  ["--definput " + definput]
        defconfig += ["--defoutput " + target + "{000a0000}.def" ]
        defconfig += ["--unfrozen" ]
        defconfig += ["--dso " + os.environ["EPOCROOT"] + "EPOC32\RELEASE\ARMV5\LIB\\" + target + ".dso"]
        defconfig = " ".join( defconfig )

        uid1 = TARGETTYPE_UID_MAP[TARGETTYPE_DLL]#"0x10000079" # DLL


    ELF2E32 = ELF2E32 % { "EPOCROOT"    : EPOCROOT,
                          "CAPABILITIES": "+".join( capabilities ),
                          "TARGET"      : target,
                          "RELEASE"     : RELEASE,
                          "WORKING_DIR" : os.path.abspath("."),
                          "TARGETTYPE"  : elf_targettype,
                          "UID1"        : uid1,
                          "UID2"        : uid2,
                          "UID3"        : uid3,
                          "DEFCONFIG"   : defconfig }

    elf2e32_output = r"%(EPOCROOT)sEPOC32\RELEASE\GCCE\%(RELEASE)s\\" % \
                        { "EPOCROOT" : EPOCROOT,
                          "RELEASE"  : RELEASE }    

    elf2e32 = Builder( action     = ELF2E32,
                       src_suffix = ".noelfexe",
                       suffix     = "." + targettype,
                       #prefix     = elf2e32_output,
                       #chdir      = elf2e32_output,
                       single_source = True,

                       #emitter    = elf_targets )#elf2e32_output + target + ".exe" )#, prefix = elf2e32_output )
                     )        
     
    env = Environment (
                    ENV = os.environ,
                    CXX = r'arm-none-symbianelf-g++',
                    #CCFLAGS = '-O2',
                    CPPPATH = INCLUDES + includes,
                    CPPDEFINES = defines,
                    CXXFLAGS = WARNINGS + " -x c++ -include " + COMPILER_INCLUDE,
                    INCPREFIX = "-I ",
                    
                    # Linker settings
                    LINK    = r'"arm-none-symbianelf-ld"',
                    LIBPATH = [ PATH_ARM_TOOLCHAIN + x for x in [
                                r"\..\lib\gcc\arm-none-symbianelf\3.4.3",
                                r"\..\arm-none-symbianelf\lib"
                                ] 
                              ],
                    LINKFLAGS     = LINKFLAGS,
                    LIBS          = LIBRARIES,
                    LIBLINKPREFIX = " ",
                    PROGSUFFIX    = ".noelfexe"
                )
    env.Append( BUILDERS = { "Elf" : elf2e32 } )

    return env



#OUTPUT_FOLDER_TEMPLATE = "%(COMPILER)_%(RELEASE)s\\%(TARGET)s_%(TARGETTYPE)s"

def SymbianProgram( target, targettype, sources, includes,
                    libraries, uid2 = "0x0", uid3 = "0x0",
                    definput = None, capabilities = None,
                    icons = None, resources = None,
                    **kwargs ):
    """
    Compiles sources using selected compiler.
    Converts resource files.
    Converts icon files.
    @param capabilities: Used capabilities. Default: FREE_CAPS
    @param **kwargs: Keywords passed to C{getenvironment()}
    @return: Last Command. For setting dependencies.
    """

    if capabilities is None:
        capabilities = FREE_CAPS
    
    # Check if stuff exists
    checked_paths = []
    checked_paths.extend( sources )
    checked_paths.extend( includes )
    if resources is not None:
        checked_paths.extend( resources )

    for x in checked_paths:
        if not os.path.exists( x ):
            raise IOError( x + " does not exist")


    # Is this Symbian component enabled?
    component_name = ".".join( [ target, targettype] ).upper()
    #print COMPONENTS
    if COMPONENTS is not None:
        if component_name not in COMPONENTS:
            print "Symbian component", component_name, "ignored"
            return None

    print "Getting dependencies for", ".".join( [target, targettype] )

    #if icons is None:
    #    icons = []
    OUTPUT_FOLDER = get_output_folder(COMPILER,RELEASE, target, targettype )
    sources = [ OUTPUT_FOLDER + "\\" + x for x in sources ]
    # This is needed often
    FOLDER_TARGET_TUPLE = ( OUTPUT_FOLDER, target )
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs( OUTPUT_FOLDER )

    # Just give type of the file
    TARGET_RESULTABLE   = "%s\\%s" % FOLDER_TARGET_TUPLE + "%s"

    env = getenvironment( target, targettype,
                          includes,
                          libraries,
                          uid2, uid3,
                          definput = definput,
                          capabilities = capabilities,
                          **kwargs )
    env.BuildDir(OUTPUT_FOLDER, ".")
    #print sources[0]
    #env.BuildDir(OUTPUT_FOLDER, os.path.dirname(sources[0]), duplicate=0)

    #-------------------------------------------------------------- Create icons
    # Copy for emulator at the end using this list, just like binaries.
    def convert_icons():

#
#        copy_icons_cmds = []
#        for icon_source in converted_icons:
#            if COMPILER == COMPILER_WINSCW:
#                # Copy to SDK to be used with simulator
#                copy_icons_cmds.append( r"copy %s \epoc32\release\WINSCW\UDEB\Z\resource\apps\\" % ( icon_source ) )
#                #env.Command( sdkfolder + "\\" + target_filename, copysource, df )
#
#            # Last to avoid copying to installfolder if sdkfolder fails
#            copy_icons_cmds.append( r"copy %s %s" % ( icon_source, icon_install ) )
#            result_path =  icon_install+ "\\" + os.path.basename(icon_source)
#            env.Command( result_path, icon_source, copy_icons_cmds )

        if icons is not None:

            result_install = COMPILER + "\\resource\\apps\\"
            sdk_resource = r"\EPOC32\DATA\Z\resource\apps\%s"

            if not os.path.exists(result_install): os.makedirs(result_install)
            result_install += "%s"

            # Creates 32 bit icons
            convert_icons_cmd = r'\epoc32\tools\mifconv "%s" /c32 "%s"'

            # TODO: Accept 2-tuple, first is the source, second: resulting name
            icon_target_path = OUTPUT_FOLDER + "\\%s_aif.mif"
            icon_targets = [] # Icons at WINSCW\...
            sdk_icons    = [] # Icons at \epoc32
            copyres_cmds = [] # Commands to copy icons from WINSCW\ to \epoc32
            for x in icons:
                tmp = icon_target_path % ( target )
                icon_targets.append( tmp )
                # Execute convert
                env.Command( tmp, x, convert_icons_cmd % ( tmp, x ) )

                sdk_target = sdk_resource % os.path.basename(tmp)
                copyres_cmds.append( "copy %s %s" % ( tmp, sdk_target ) )
                sdk_icons.append( sdk_target )
            #import pdb;pdb.set_trace()
            return env.Command( sdk_icons, icon_targets, copyres_cmds )

            #return icon_targets

        return None

    converted_icons = convert_icons()

    #---------------------------------------------------- Convert resource files
    def convert_resources():
        """
        Compile resources and copy for sis creation and for simulator.
        .RSC
            -> \EPOC32\DATA\Z\resource\apps\
            -> \Epoc32\release\winscw\udeb\z\resource\apps\
        _reg.RSC
            -> epoc32\release\winscw\udeb\z\private\10003a3f\apps\
            -> epoc32\DATA\Z\private\10003a3f\apps\
        .RSG     -> epoc32\include\
        """
        converted_resources = []
        resource_headers = []

        if resources is not None:
            res_includes = "-I " + " -I ".join( includes + INCLUDES )
            convert_res_cmd = " ".join( [
                r'perl -S %sepoc32\tools\epocrc.pl' % EPOCROOT,
                r'  -m045,046,047 -I-',
                res_includes,
                r'-DLANGUAGE_SC ',
                r'-u "%(SOURCEPATH)s" ',
                '-o"%(OUTPUT_FOLDER)s\\%(RESOURCE)s.RSC"',
                '-h"%(OUTPUT_FOLDER)s\\%(RESOURCE)s.rsg"',
                #r'-t"\EPOC32\BUILD\Projects\LoggingServer\LoggingServerGUI\group\LOGGINGSERVERGUI\WINSCW"',
                #r'-l"Z\resource\apps:\Projects\LoggingServer\LoggingServerGUI\group"',
            ] )

            # Make the resources dependent on previous resource
            # Thus the resources must be listed in correct order.
            prev_resource = None
            
            for rss_path in resources:
                rss_notype = ".".join(os.path.basename(rss_path).split(".")[:-1]) # ignore rss

                cmd = convert_res_cmd % { "OUTPUT_FOLDER" : OUTPUT_FOLDER,
                                          "RESOURCE"      : rss_notype,
                                          "SOURCEPATH"    : rss_path }

                converted_rsg = OUTPUT_FOLDER + "\\%s.RSG" % rss_notype
                converted_rsc = OUTPUT_FOLDER + "\\%s.RSC" % rss_notype

                result_paths  = [ ]
                copyres_cmds = [ ]

                converted_resources.append( converted_rsc )

                # Compile resource files
                res_compile_command = env.Command( [converted_rsc, converted_rsg], rss_path, cmd )
                env.Depends(res_compile_command, converted_icons)

                includefolder = EPOCROOT + "epoc32\\include"
                installfolder = COMPILER + r"\private\10003a3f\import\apps"
                if not os.path.exists(installfolder): os.makedirs(installfolder)

                ## Copy files for sis creation and for simulator
                def copy_file( source_path, target_path ):
                    copy_cmd = "copy %s %s" % ( source_path, target_path )
                    copyres_cmds.append( copy_cmd )
                    result_paths.append( target_path )

                rsc_filename = "%s.%s" % ( rss_notype, "rsc" )
                installfolder += "\\" + rsc_filename
                # Copy to sis creation folder
                copy_file( converted_rsc, installfolder )

                # Copy to \epoc32\include\
                includefolder += "\\%s.%s" % ( rss_notype, "rsg" )
                copy_file( converted_rsg, includefolder )

                # Add created header to be added for build dependency
                resource_headers.append( includefolder )

                # _reg files copied to \EPOC32\DATA\Z\private\10003a3f\apps\ on simulator
                if "_reg" in rss_path.lower():
                    path_private_simulator = r"\EPOC32\DATA\Z\private\10003a3f\apps\%s" % rsc_filename
                    copy_file( converted_rsc, path_private_simulator )

                    path_private_simulator = r"\Epoc32\release\winscw\udeb\z\private\10003a3f\apps\%s" % rsc_filename
                    copy_file( converted_rsc, path_private_simulator )

                else: # Copy normal resources to resource\apps folder
                    path_resource_simulator = r"\EPOC32\DATA\Z\resource\apps\%s" % rsc_filename
                    copy_file( converted_rsc, path_resource_simulator )

                    path_resource_simulator = r"\Epoc32\release\winscw\udeb\z\resource\apps\%s" % rsc_filename
                    copy_file( converted_rsc, path_resource_simulator )

                header_rsg = env.Command( result_paths, converted_resources, copyres_cmds )

                # Depend on previous
                if prev_resource is not None:
                    env.Depends( res_compile_command, prev_resource )
                prev_resource = header_rsg
                
        return converted_resources, resource_headers

    converted_resources, resource_headers = convert_resources()

    # To be copied to \EPOC32\RELEASE\WINSCW\UDEB\
    output_libpath = None
    returned_command = None

    if COMPILER == COMPILER_GCCE:
        temp_dll_path = TARGET_RESULTABLE % ("._tmp_" + targettype )
        resultables = [ temp_dll_path ]

        build_prog = env.Program( resultables, sources )
        env.Depends( build_prog, converted_icons )
        env.Depends( build_prog, resource_headers )
        env.Elf( TARGET_RESULTABLE % ( "" ), temp_dll_path )
        return
    else:

        # Compile sources ------------------------------------------------------
        # Creates .lib
        targetfile = target + "." + targettype

        def build_uid_cpp(target, source, env):
           """Create .UID.CPP for simulator"""
           template = ""
           if targettype == TARGETTYPE_EXE:
               ## TODO: Set uid's
               template = TARGET_UID_CPP_TEMPLATE_EXE % { "UID3": uid3 }
           else:
               template = TARGET_UID_CPP_TEMPLATE_DLL

           f = open(uid_cpp_filename,'w');f.write( template );f.close()
           return None

        # Create <target>.UID.CPP from template---------------------------------
        uid_cpp_filename = TARGET_RESULTABLE % ".UID.cpp"

        bld = Builder(action = build_uid_cpp,
                      suffix = '.UID.cpp' )
        env.Append( BUILDERS = {'CreateUID' : bld})
        env.CreateUID(uid_cpp_filename, sources)

        # We need to include the UID.cpp also
        sources.append( uid_cpp_filename )

        # Compile the sources. Create object files( .o ) and temporary dll.
        output_lib    = ( targettype in DLL_TARGETTYPES )
        temp_dll_path = TARGET_RESULTABLE % ("._tmp_" + targettype )
        resultables = [ temp_dll_path ]

        if output_lib:
            # No libs from exes
            libname = target + ".lib"
            resultable_path = TARGET_RESULTABLE % "._tmp_lib"
            resultables.append(resultable_path )
            #resultables.append( TARGET_RESULTABLE % ".inf" )
            output_libpath = ( TARGET_RESULTABLE % ".lib",
                                r"\EPOC32\RELEASE\%s\%s\\" % ( COMPILER, RELEASE ) + libname )

        build_prog = env.Program( resultables, sources )
        # Depends on the used libraries. This has a nice effect since if,
        # this project depends on one of the other projects/components/dlls/libs
        # the depended project is automatically built first.
        env.Depends( build_prog, [ r"\EPOC32\RELEASE\%s\%s\\%s" % ( COMPILER, RELEASE, libname ) for libname in libraries] )
        env.Depends( build_prog, converted_icons )
        env.Depends( build_prog, resource_headers )
        
        if output_lib:
            # Create .inf file

            if definput is not None:# and os.path.exists(definput):
                definput = '-Frzfile "%s" ' % definput
            else:
                definput = ""

            action = "\n".join( [
                # Creates <target>.lib
                'mwldsym2.exe -S -show only,names,unmangled,verbose -o "%s" "%s"' % ( TARGET_RESULTABLE % ".inf", TARGET_RESULTABLE % "._tmp_lib" ),
                # Creates def file
                r'perl -S %EPOCROOT%epoc32\tools\makedef.pl -absent __E32Dll ' + '-Inffile "%s" ' % ( TARGET_RESULTABLE % ".inf" )
                + definput
                + ' "%s"' % ( TARGET_RESULTABLE % '.def' ) ] )
            #print action
            #BuildDir('build', 'src', duplicate=0)
            defbld = Builder( action = action,
                              ENV = os.environ )
            env.Append( BUILDERS = {'Def' : defbld} )
            env.Def( #COMPILER+ "\\" + target + ".inf",
                       #TARGET_RESULTABLE % ".inf",
                       TARGET_RESULTABLE % ".def",
                       TARGET_RESULTABLE % "._tmp_lib" )

        # NOTE: If build folder is changed this does not work anymore.
        # List compiled sources and add to dependency list
        object_paths = [ ".".join( x.split(".")[:-1] ) + ".o" for x in sources ]

        # Sources depend on the headers generated from .rss files.
        env.Depends( object_paths, resource_headers )

        # Get the lookup folders from source paths.
        object_folders = [ os.path.dirname( x ) for x in object_paths ]

        # Needed to generate the --search [source + ".cpp" -> ".o",...] param
        objects = [ os.path.basename( x ) for x in object_paths ]
        objects = " ".join( objects )

        libfolder = "%EPOCROOT%EPOC32\RELEASE\WINSCW\UDEB\\"
        libs      = [ libfolder + x for x in libraries]

        if targettype in DLL_TARGETTYPES:

            env.Command( TARGET_RESULTABLE % ("." + targettype ), [ temp_dll_path, TARGET_RESULTABLE % ".def" ],
            [
                " ".join( [
                            'mwldsym2.exe -msgstyle gcc',
                            '-stdlib %EPOCROOT%EPOC32\RELEASE\WINSCW\UDEB\EDLL.LIB -noentry',
                            '-shared -subsystem windows',
                            '-g %s' % " ".join( libs ),
                            '-o "%s"' % temp_dll_path,
                            '-f "%s"' % ( TARGET_RESULTABLE % ".def" ),
                            '-implib "%s"' % ( TARGET_RESULTABLE % ".lib" ),
                            '-addcommand "out:%s.%s"' % ( target, targettype ),
                            '-warnings off',
                            '-l %s' % " -l ".join( set(object_folders) ),
                            '-search ' + objects,
                          ]
                        )
            ]
            )
        elif targettype == TARGETTYPE_EXE:
            env.Command( TARGET_RESULTABLE % ".exe", temp_dll_path,
                [
                " ".join( [ 'mwldsym2.exe',
                            '-msgstyle gcc',
                            '-stdlib %EPOCROOT%EPOC32\RELEASE\WINSCW\UDEB\EEXE.LIB',
                            '-m "?_E32Bootstrap@@YGXXZ"',
                            '-subsystem windows',
                            '-g %s' % " ".join( libs ),
                            '-o "$TARGET"',
                            '-noimplib',
                            '-l %s' % " -l ".join( set( object_folders ) ),
                            '-search ' + objects,
                          ]
                        )
                ]
            )

    # NOTE: For some reason SCons does not understand drive letters with targets

    # Installer folder
    sdkfolder     = r"%sEpoc32\release\%s\%s\\" % (
                        EPOCROOT,
                        COMPILER,
                        RELEASE
                    )

    def copy_result_binary( ):
        """Copy the linked binary( exe, dll ) for emulator
        and to resultables folder.
        """
        installfolder = COMPILER + "\\sys\\bin\\"
        if not os.path.exists(installfolder): os.makedirs(installfolder)
        installfolder += "%s.%s" % ( target, targettype )

        postcommands = []
        copysource = TARGET_RESULTABLE % ( "."+targettype)
        target_filename = target + "." + targettype
        sdkpath       = sdkfolder + "\\" + target_filename

        installed = []
        if COMPILER == COMPILER_WINSCW:
            # Copy to SDK to be used with simulator
            postcommands.append( "copy %s %s" % ( copysource, sdkpath ) )
            installed.append( sdkpath )
            #env.Command( sdkfolder + "\\" + target_filename, copysource, df )



        if output_libpath is not None:
            s,t = output_libpath
            postcommands.append( "copy %s %s" % ( s, t ) )
            installed.append( t )

        # Last to avoid copying to installfolder if sdkfolder fails
        postcommands.append( "copy %s %s" % ( copysource, installfolder ) )
        installed.append(installfolder )
        returned_command = env.Command( installed , copysource, postcommands )

    #copy_icons()
    copy_result_binary()

    return returned_command


