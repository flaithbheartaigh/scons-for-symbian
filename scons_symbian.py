"""
Main S4S module
"""
#pylint: disable-msg=E0611
from SCons.Builder import Builder
from SCons.Script import (Command, Copy, DefaultEnvironment, Install, Mkdir, Clean, Default)
from arguments import * #IGNORE:W0611
from os.path import join, basename
import mmp_parser
import colorizer
import gcce
import os
import symbian_pkg
import winscw
import rcomp
import textwrap
#pylint: enable-msg=E0611

__author__ = "Jussi Toivola"
__license__ = "MIT License"

# TODO: freeze # perl -S /epoc32/tools/efreeze.pl %(FROZEN)s %(LIB_DEFS)s

#: Handle to console for colorized output( and process launching )
_OUTPUT_COLORIZER = colorizer.OutputConsole()

# Set EPOCROOT as default target, so the stuff will be built for emulator.
Default( EPOCROOT )
Default( "." )

print "Building", COMPILER, RELEASE
print "Defines", CMD_LINE_DEFINES

# in template
# UID1 = 0x100039ce for exe
# UID1 = 0x00000000 for dll

def _create_environment( *args, **kwargs ):
    """Environment factory. Get correct environment for selected compiler."""
    env = None
    
    if COMPILER == COMPILER_GCCE:
        env = gcce.create_environment( *args, **kwargs )
    elif COMPILER == COMPILER_WINSCW:
        env = winscw.create_environment( *args, **kwargs )
    else:
        msg = "Error: Environment for '%s' is not implemented" % COMPILER
        raise NotImplementedError( msg )
    return env


def SymbianPackage( package, ensymbleargs = None, pkgargs = None,
                    pkgfile = None, extra_files = None, source_package = None,
                    env=None, startonboot = None ):
    """
    Create Symbian Installer( sis ) file. Can use either Ensymble or pkg file.
    To enable creation, give command line arg: dosis=true
    
    @param package: Name of the package.
    @type package: str
    
    @param pkgargs: Arguments to PKG generation. Disabled if none, use empty dict for simple enable.
                    To enable signing, give at least both cert and keys, which point to the
                    respective files. passwd key can be used for password.
                    If pkgfile is not given, package name is converted to pkg extension and used instead.
                    The signed sis file gets extension SIGNSIS_OUTPUT_EXTENSION defined in constants.py
                    
    @type pkgargs: dict
    
    @param ensymbleargs: Arguments to Ensymble simplesis.
    @type ensymbleargs: dict 
    
    @param source_package: Use data from another package for pkg generation.
                           Equals to 'package' if None.
        
    @param pkgfile: Path to pkg file.
    @type pkgfile: str
    
    @param startonboot: Name of the executable to be started on boot
    @type startonboot: str
    
    @param extra_files: Copy files to package folder and install for simulator( to SIS with Ensymble only )
    """                     
    # Skip processing to speed up help message                    
    if HELP_ENABLED: return
    if not env:
        env = DefaultEnvironment()
        
    if ensymbleargs is not None and pkgargs is not None:
        raise ValueError( "Trying to use both Ensymble and PKG file. Which one do you really want?" )
    else:
        if ensymbleargs is None:
            ensymbleargs = {}
    
    if source_package is None:
        source_package = package
        
    if extra_files is not None:
        pkg = PKG_HANDLER.Package( package )
        
        for target, source in extra_files:
            pkg[source] = target
            
            ToPackage( DefaultEnvironment(), None, package, target, source, toemulator = False )
                    
            if COMPILER == COMPILER_WINSCW:
                Install( join( FOLDER_EMULATOR_C, target ), source )
        
    def create_pkg_file( pkgargs ):
        
        if pkgargs is None:
            pkgargs = {}
        
        PKG_HANDLER.PackageArgs( package ).update( pkgargs )
        PKG_HANDLER.pkg_sis[pkgfile] = source_package
        Command( pkgfile, PKG_HANDLER.pkg_files[package].keys(),
                        PKG_HANDLER.GeneratePkg, ENV = os.environ )
        
        
    if COMPILER != COMPILER_WINSCW:
        if pkgargs is not None:     
            if pkgfile is None:
                pkgfile = symbian_pkg.GetPkgFilename(package)
            create_pkg_file( pkgargs )
    
    def __create_boot_up_resource( target, source, env):
        """Create boot up resource file"""
        # Notice that the resource must ALWAYS be copied to C:
        template = r"""
        #include <startupitem.rh>
 
        RESOURCE STARTUP_ITEM_INFO startexe
        {
            executable_name = "c:\\sys\\bin\\%(APPNAME)s";
            recovery = EStartupItemExPolicyNone;
        }
        """
        
        content = template % { "APPNAME" : startonboot }
                
        content = textwrap.dedent(content)
        print content
        
        f = open( target[0].path, 'w' )
        f.write(content)
        f.close()
    
    
    def _makeBootUpResource( ):
        """Create resource file for starting executable on boot and compile it"""
        
        if not startonboot: return
        
        output_folder = get_output_folder( COMPILER, RELEASE, startonboot, "rss" )
        
        uid = PKG_HANDLER.PackageArgs(package)["uid"]
        
        uid = uid.replace("0x", "" )
        
        rssfilepath = join( output_folder, "[%s].rss" % uid )
        env.Command( rssfilepath, None, __create_boot_up_resource )
        
        rscfilepath = join( output_folder, "[%s].rsc" % uid )
        rsgfilepath = join( output_folder, "%s.rsg" % uid )
        
        rcomp.RComp( env, rscfilepath, rsgfilepath,
                             rssfilepath,
                             "-v -m045,046,047",
                             SYSTEM_INCLUDES,
                             [PLATFORM_HEADER],
                             [ 'LANGUAGE_SC'])
        
        ToPackage(env, { "C" : ".*[.](rsc)" }, package, 
                  "private/101f875a/import/", rscfilepath, toemulator=False)
        
        if COMPILER == COMPILER_WINSCW:
            env.Install( join( EPOC32_DATA ), rscfilepath ) 
    
    #---------------------------------------------------- Create boot up API resource
    _makeBootUpResource()
                
    def create_install_file( installed ):
        "Utility for creating an installation package using Ensymble"
        from ensymble.cmd_simplesis import run as simplesis
                
        if pkgfile is None and ENSYMBLE_AVAILABLE:
                                
            def ensymble( env, target = None, source = None ): #IGNORE:W0613
                """ Wrap ensymble simplesis command. """
                cmd = []
                for x in ensymbleargs:
                    cmd += [ "%s=%s" % ( x, ensymbleargs[x] ) ]
                    
                cmd += [ join( PACKAGE_FOLDER, package ), package ]
                
                try:
                    print "Running simplesis:" + str( cmd )
                    simplesis( "scons", cmd )
                except Exception, msg:#IGNORE:W0703
                    import traceback
                    traceback.print_exc()                
                    return str( msg )
                                                                                                
            Command( package, installed, ensymble, ENV = os.environ )        
        
        elif pkgfile is not None:
            result = symbian_pkg.Makesis( pkgfile, 
                                          package, 
                                          installed = PKG_HANDLER.pkg_files[package].keys() )
                        
            cert = pkgargs.get("cert", None )
            key  = pkgargs.get("key", None)
            if cert and key:
                sisx = package.split(".")
                sisx = ".".join( sisx[:-1] ) + SIGNSIS_OUTPUT_EXTENSION                
                env.Depends( sisx, package )
                env.Depends( sisx, PKG_HANDLER.pkg_files[package].keys() + result )
                
                passwd = pkgargs.get( "passwd", "" )
                result.append( symbian_pkg.SignSis( sisx, package, pkgargs["cert"], pkgargs["key"], passwd ) )
 
    if DO_CREATE_SIS:
        return create_install_file( PKG_HANDLER.Package(package).keys() )

def SymbianHelp( source, uid, env = None ):
    """ Generate help files for Context Help
    @param source: Help project file .cshlp"
    @uid: UID of the application.
    
    @return: generated .hlp and .hrh files.
    @rtype: 2-tuple
    """
    import cshlp
    if env is None:
        env = DefaultEnvironment()
        
    helpresult = cshlp.CSHlp( DefaultEnvironment(), source, uid )
    return helpresult
    
#: Holds the file source->target paths for each package
#: This information is be used to generate the pkg file.
PKG_HANDLER = symbian_pkg.PKGHandler()

def ToPackage( env = None, package_drive_map = None, package = None,
               target = None, source = None, toemulator = True ):
    """Insert file into package.
    @param env: Environment. DefaultEnvironment() used if None.
        
    @param package_drive_map: Regular expression drive mapping. You can also
                              tell the path directly on 'target', but do not
                              use this then.
    @rtype package_drive_map: dict
    
    @param package: Package(.sis) to be used. Nothing done, if None.
    @param target: Folder on device
    @param source: Source path of the file    
    @param toemulator: Flag to determine if the file is installed for SDK's emulator.
    
    """
    for attr in ["target", "source"]:
        notnone = locals()[attr]
        if notnone is None:            
            raise AttributeError( "Error: '%s' is None." % attr )
    
    if env is None:
        env = DefaultEnvironment()
        
    # Just skip this then    
    if package is None:
        return
        
    import re
    # WARNING: Copying to any/c/e is custom Ensymble feature.
    drive = ""
    
    # Gets reference.
    pkg = PKG_HANDLER.Package( package )
    
    if package_drive_map is not None:
            
        # Goes to any by default
        drive = "any"    
        filename = os.path.basename( source )
        
        for d in package_drive_map:
            regexp = package_drive_map[d]       
            if type( regexp ) == str: 
                regexp = re.compile( regexp )
                package_drive_map[d] = regexp
            
            if regexp.match( filename ):
                drive = d
                break
    
    # Add to pkg generator
    pkgsource = join( PACKAGE_FOLDER, package, drive, target, basename( source ) )
    pkg[pkgsource] = join( drive, target, basename( source ) )
    env.Depends( symbian_pkg.GetPkgFilename( package ), join( PACKAGE_FOLDER, package, pkg[pkgsource] ) )
    
    if drive == "":
        pkg[pkgsource] = join( "any", target, basename( source ) )    
    
    # Do the copy
    cmd = env.Install( join( PACKAGE_FOLDER, package, drive, target ), source )  
    Clean( cmd,join( PACKAGE_FOLDER, package) )    
       
    if toemulator and COMPILER == COMPILER_WINSCW:
        env.Install( join( FOLDER_EMULATOR_C, target ), source )
        
    return cmd

def SymbianProgram( target, targettype = None, #IGNORE:W0621
                    sources = None, includes = None,
                    libraries = None, uid2 = None, uid3 = None,
                    sid = None,
                    definput = None, capabilities = None,
                    icons = None, resources = None,
                    rssdefines = None,
                    defines = None,
                    help = None,
                    sysincludes = None,
                    mmpexport = None,
                    # Sis stuff
                    package = "",
                    package_drive_map = None,
                    extra_depends = None,
                    **kwargs):
    """
    Main function for compiling Symbian applications and libraries. 
    Handles the whole process of source and resource compiling 
    and SIS installer packaging. 
    
    @param target: Name of the module without file extension.
                    If the name ends with .mmp, the .mmp file is used for 
                    defining the module.
    @type target: str 
    
    @param targettype: Type of the program. One of L{arguments.TARGETTYPES}.    
    @type targettype: str
    
    @param sources:     List of paths to sources to compiler
    @type sources: list
    
    @param includes:    List of folders to be used for finding user headers.
    @type includes: list
    
    @param sysincludes:  List of folders to be used for finding system headers.
    @type sysincludes: list
    
    @param sid: Secure id. Defaults to uid3.
    @type sid: str/hex
    
    @param mmpexport: Path to the generated MMP
    @type mmpexport: str
    
    @param definput:    Path to .def file containing frozen library entrypoints.
    @type definput: str
    
    @param icons:       List of icon files to compile
    @type icons: list
    
    @param resources:   List of paths to .rss files to compile. 
                        See rssdefines param for giving CPP macros.
    @type resources: list          
    
    @param libraries: Used libraries.
    @type libraries: list
    
    @param capabilities: Used capabilities. Default: FREE_CAPS
    @type capabilities: list
    
    @param defines: Preprocess definitions.
    @type defines: list
    
    @param rssdefines: Preprocessor definitions for resource compiler.
    @type rssdefines: list
    
    @param package:       Path to installer file. If given, an installer is automatically created.
                          The files are copied to L{arguments.PACKAGE_FOLDER} and
                          Ensymble is used to create an installer package with simplesis command.

    @type package: str
    
    @param package_drive_map: For custom Ensymble with drive destination support.
                              Map files to drives by using regular expressions.
                              For example, to map .mif and .rsc files to C drive:
                                package_drive_map = { "C" : ".*[.](mif|rsc)" }
                              The files goes to 'any' folder by default.
                              
                              Disabled if None. Normal Ensymble behavior used.
                                
    @type  package_drive_map: dict
                                  
    @param extra_depends: External files which must be built prior the app
    @type extra_depends: list
     
    @param kwargs: Additional keywords passed to selected compiler environment
                   factory: L{gcce.create_environment}, L{winscw.create_environment}
    
    @return: Last Command. For setting dependencies.
    
    """
    
    # Transforms arguments into keywords
    kwargs.update( locals() )
     
    handler = SymbianProgramHandler( **kwargs )
    return handler.Process()

class SymbianProgramHandler(object):
    """Internal class for handling the SymbianProgram function call"""
    def __init__(self, **kwargs):
        
        #: Compiler environment
        self._env = None
        self.target = None
        self.extra_depends = None
        self.sysincludes = None
        self.origsources = [] # Sources not altered for BuildDir        
        # Store the keywords as instance attributes        
        for arg in kwargs:
            setattr( self, arg, kwargs[arg] )
        
        #: Folder for compiler releasables.
        self.output_folder = get_output_folder( COMPILER, RELEASE, self.target, self.targettype )
        
        
    def _isComponentEnabled(self):
        """Is the component enabled."""
        component_name = ".".join( [ self.target, self.targettype] ).lower()
        
        if COMPONENTS is not None:
            inlist = ( component_name in COMPONENTS )
            if inlist and not COMPONENTS_EXCLUDE:
                pass
            elif not inlist and COMPONENTS_EXCLUDE:
                pass
            else:
                print "Ignored Symbian component", component_name
                return False
        
        print "Getting dependencies for", component_name
        
        return True
    
    def _handleIcons(self):
        """Sets self.converted_icons"""   
        #TODO: Create main interface SymbianIcon for generic icons
        
        # Copy for emulator at the end using this list, just like binaries.
        self.converted_icons = []  
        
        if self.icons is None:
            return
                                               
        sdk_data_resource = EPOCROOT + r"epoc32/DATA/Z/resource/apps/%s"
        sdk_resource = join( EPOCROOT + r"epoc32", "release", COMPILER,
                         RELEASE, "z", "resource", "apps", "%s" )

        # Creates 32 bit icons
        convert_icons_cmd = ( EPOCROOT + r'epoc32/tools/mifconv "%s" /c32 "%s"' ).replace( "\\", "/" )
        
        # TODO: Accept 2-tuple, first is the source, second: resulting name
        icon_target_path = join( self.output_folder, "%s_aif.mif" )
        icon_targets = [] # Icons at WINSCW/...
        sdk_icons = [] # Icons at /epoc32
        copyres_cmds = [] # Commands to copy icons from WINSCW/ to /epoc32
        
        for x in self.icons:
            tmp = icon_target_path % ( self.target )
            icon_targets.append( tmp )
            
            # Execute convert
            self._env.Command( tmp, x, convert_icons_cmd % ( tmp, x ) )
            
            iconfilename = os.path.basename( tmp )
            
            sdk_target = sdk_resource % iconfilename
            copyres_cmds.append( Copy( sdk_target, tmp ) )
            sdk_icons.append( sdk_target )
            
            sdk_target = sdk_data_resource % iconfilename
            copyres_cmds.append( Copy( sdk_target, tmp ) )
            sdk_icons.append( sdk_target )
            
            ToPackage( self._env, self.package_drive_map, self.package,
                join( "resource", "apps" ),
                tmp, toemulator = False ) 
                       
        self._env.Command( sdk_icons, icon_targets, copyres_cmds )
        self.converted_icons = sdk_icons            
    
    def _copyResultBinary(self):
        """Copy the linked binary( exe, dll ) for emulator
        and to resultables folder.
        """
        
        env = self._env
        installfolder = [ ]

        if self.targettype != TARGETTYPE_LIB:
            installfolder += ["sys", "bin" ]
        else: # Don't install libs to device.
            installfolder += ["lib"]
            
        installfolder = join( *installfolder )
        #Mkdir( installfolder )
        
        #installpath = join( installfolder, "%s.%s" % ( self.target, self.targettype ) )
        
        # Combine with installfolder copying. 
        #TODO: Not needed anymore since EPOCROOT is default target.
        postcommands = []
        copysource = self._target_resultable % ( "." + self.targettype )
        target_filename = self.target + "." + self.targettype
        sdkpath = join( SDKFOLDER, target_filename )

        installed = []
        if COMPILER == COMPILER_WINSCW:
            # Copy to SDK to be used with simulator
            postcommands.append( Copy( sdkpath, copysource ) )
            installed.append( sdkpath )

        if self.output_libpath is not None:
            if (COMPILER == COMPILER_WINSCW and self.targettype != TARGETTYPE_LIB) or \
                COMPILER == COMPILER_GCCE and self.targettype == TARGETTYPE_LIB :
                
                s, t = self.output_libpath
                postcommands.append( Copy( t, s ) )
                installed.append( t )
            
        # Last to avoid copying to installpath if sdkfolder fails
        #postcommands.append( Copy( installpath, copysource ) )
        #installed.append( installpath )
        
        returned_command = env.Command( installed, #IGNORE:W0612
                                        copysource,
                                        postcommands )
        
        if self.targettype != TARGETTYPE_LIB:
            ToPackage( env, self.package_drive_map, self.package,
                    installfolder,
                    copysource, toemulator = False )
        else:  # Don't install libs to device.
            ToPackage( env, None, None,
                    "lib",
                    copysource, toemulator = False )
                    
        return installed
 
    #TODO: Create main interface SymbianResource for special resource compiling
    def _convertResources( self ):
        """
        Compile resources and copy for sis creation and for simulator.
        Sets self.resource_headers, self.converted_resources.
        .RSC
            -> /epoc32/DATA/Z/resource/apps/
            -> /epoc32/release/winscw/udeb/z/resource/apps/
        _reg.RSC
            -> epoc32/release/winscw/udeb/z/private/10003a3f/apps/
            -> epoc32/DATA/Z/private/10003a3f/apps/
        .RSG     -> epoc32/include/
        """            
        
        self.converted_resources = []
        self.resource_headers    = []
        
        if self.resources is not None:
            # Make the resources dependent on previous resource
            # Thus the resources must be listed in correct order.
            prev_resource = None
            
            for rss_path in self.resources:
                rss_notype = ".".join( os.path.basename( rss_path ).split( "." )[: - 1] ) # ignore rss
                converted_rsg = join( self.output_folder, "%s.rsg" % rss_notype )
                converted_rsc = join( self.output_folder, "%s.rsc" % rss_notype )
                self.converted_resources.append( converted_rsc )
                
                result_paths = [ ]
                copyres_cmds = [ ]

                res_compile_command = rcomp.RComp( self._env, converted_rsc, converted_rsg,
                             rss_path,
                             "-m045,046,047",
                             self.sysincludes + self.includes,
                             [PLATFORM_HEADER],
                             self.rssdefines )
                             
                self._env.Depends( res_compile_command, self.converted_icons )

                includefolder = EPOC32_INCLUDE
                
                installfolder = []
                #if package != "": 
                    #installfolder.append( package )
                if rss_notype.endswith( "_reg" ):
                    installfolder.append( join( "private", "10003a3f", "import", "apps" ) )
                else:
                    installfolder.append( join( "resource", "apps" ) )
                installfolder = os.path.join( *installfolder )
                
                # Copy files for sis creation and for simulator
                def copy_file( source_path, target_path ):
                    copy_cmd = Copy( target_path, source_path )
                    #"copy %s %s" % ( source_path, target_path )
                    copyres_cmds.append( copy_cmd )
                    result_paths.append( target_path )

                rsc_filename = "%s.%s" % ( rss_notype, "rsc" )
                # Copy to sis creation folder                
                ToPackage( self._env, self.package_drive_map, self.package,
                           installfolder, converted_rsc, toemulator = False )

                # Copy to /epoc32/include/                
                self._env.Install( includefolder, converted_rsg )#IGNORE:E1101
                includepath = join( includefolder, "%s.%s" % ( rss_notype, "rsg" ) )
                
                # Add created header to be added for build dependency
                self.resource_headers.append( includepath )

                # _reg files copied to /epoc32/DATA/Z/private/10003a3f/apps/ on simulator
                if COMPILER == COMPILER_WINSCW:
                    if "_reg" in rss_path.lower():
                        self._env.Install( join( EPOC32_DATA, "Z", "private","10003a3f","apps"), converted_rsc ) 
                        self._env.Install( join( EPOC32_RELEASE, "Z", "private","10003a3f","apps"), converted_rsc )

                    else: # Copy normal resources to resource/apps folder
                        self._env.Install( join( EPOC32_DATA, "Z", "resource","apps"), converted_rsc )
                        self._env.Install( join( EPOC32_RELEASE, "Z", "resource", "apps"), converted_rsc )


                # Depend on previous. TODO: Use SCons Preprocessor scanner.
                if prev_resource is not None:
                    self._env.Depends( rss_path, prev_resource )
                prev_resource = includepath                
    
    def _handleGCCEBuild(self):
        env = self._env
        output_lib = ( self.targettype in DLL_TARGETTYPES )
        temp_dll_path = self._target_resultable % ( "._tmp_" + self.targettype )
        resultables = [ temp_dll_path ]
        
        if output_lib:
            libname = self.target + ".dso"
            self.output_libpath = ( EPOCROOT + r"epoc32/release/%s/%s/%s" % ( "armv5", "lib", libname ) )

        build_prog = None
        if self.targettype != TARGETTYPE_LIB:
            build_prog = self._env.Program( resultables, self.sources )#IGNORE:E1101                
            
            # Depend on the libs
            for libname in self.libraries:
                env.Depends( build_prog, libname )
                
            # Mark the lib as a resultable also
            resultables = [ self._target_resultable % ( "" ) ]
            if output_lib:
                resultables.append( self.output_libpath )

            # Create final binary and lib/dso
            self._env.Elf( resultables, temp_dll_path )#IGNORE:E1101

        else:
            build_prog = env.StaticLibrary( self._target_resultable % ".lib" , self.sources )#IGNORE:E1101
            self.output_libpath = ( self._target_resultable % ".lib",
                                EPOCROOT + r"epoc32/release/armv5/%s/%s.lib" % ( RELEASE, self.target ) )
            
        return build_prog
    
    def _createUIDCPP( self, target, source, env ):#IGNORE:W0613
        """Create .UID.CPP for simulator"""
        template = ""
        
        if self.targettype == TARGETTYPE_EXE:
            template = winscw.TARGET_UID_CPP_TEMPLATE_EXE % { "UID3": self.uid3,
                                                              "SID" : self.sid }
        else:
            template = winscw.TARGET_UID_CPP_TEMPLATE_DLL
        
        f = open( target[0].path, 'w' );f.write( template );f.close()
        
        return None
            
    def _handleWINSCWBuild(self):
        # Compile sources ------------------------------------------------------
        env = self._env
        
        # Create <target>.UID.CPP from template---------------------------------
        uid_cpp_filename = self._target_resultable % ".UID.cpp"

        bld = Builder( action = self._createUIDCPP,
                      suffix = '.UID.cpp' )
        env.Append( BUILDERS = {'CreateUID' : bld} )
        env.CreateUID( uid_cpp_filename, self.sources )#IGNORE:E1101
        
        # We need to include the UID.cpp also
        self.sources.append( uid_cpp_filename )

        # Compile the sources. Create object files( .o ) and temporary dll.
        output_lib = ( self.targettype in DLL_TARGETTYPES )
        temp_dll_path = self._target_resultable % ( "._tmp_" + self.targettype )
        resultables = [ temp_dll_path ]

        if output_lib:
            # No libs from exes
            libname = self.target + ".lib"
            resultable_path = self._target_resultable % "._tmp_lib"
            resultables.append( resultable_path )
            #resultables.append( self._target_resultable % ".inf" )
            self.output_libpath = ( self._target_resultable % ".lib",
                                join( EPOC32_RELEASE, libname ) )
        
        if self.targettype != TARGETTYPE_LIB:
            build_prog = env.Program( resultables, self.sources )#IGNORE:E1101
            # Depends on the used libraries. This has a nice effect since if,
            # this project depends on one of the other projects/components/dlls/libs
            # the depended project is automatically built first.
            env.Depends( build_prog, [ join( EPOC32_RELEASE, libname ) for libname in self.libraries] )
            
        else:
            build_prog = env.StaticLibrary( self._target_resultable % ".lib" , self.sources )#IGNORE:E1101
            self.output_libpath = ( self._target_resultable % ".lib",
                                join( EPOC32_RELEASE, "%s.lib" % ( self.target ) ) )
        
        if output_lib and self.targettype != TARGETTYPE_LIB:
            # Create .inf file
            definput = self.definput
            if definput is not None:# and os.path.exists(definput):
                definput = '-Frzfile "%s" ' % definput
            else:
                definput = ""

            action = "\n".join( [
                # Creates <target>.lib
                'mwldsym2.exe -S -show only,names,unmangled,verbose -o "%s" "%s"' % ( self._target_resultable % ".inf", self._target_resultable % "._tmp_lib" ),
                # Creates def file
                r'perl -S %EPOCROOT%epoc32/tools/makedef.pl -absent __E32Dll ' + '-Inffile "%s" ' % ( self._target_resultable % ".inf" )
 + definput
 + ' "%s"' % ( self._target_resultable % '.def' ) ] )

            defbld = Builder( action = action,
                              ENV = os.environ )
            env.Append( BUILDERS = {'Def' : defbld} )
            env.Def( self._target_resultable % ".def", #IGNORE:E1101
                     self._target_resultable % "._tmp_lib" )

        # NOTE: If build folder is changed this does not work anymore.
        # List compiled sources and add to dependency list
        object_paths = [ ".".join( x.split( "." )[: - 1] ) + ".o" for x in self.sources ] #IGNORE:W0631
        
        # Sources depend on the headers generated from .rss files.
        env.Depends( object_paths, self.resource_headers )

        # Get the lookup folders from source paths.
        object_folders = [ os.path.dirname( x ) for x in object_paths ]

        # Needed to generate the --search [source + ".cpp" -> ".o",...] param
        objects = [ os.path.basename( x ) for x in object_paths ]
        objects = " ".join( objects )

        libfolder = "%EPOCROOT%epoc32/release/winscw/udeb/"
        libs = [ libfolder + x for x in self.libraries]
    
        if self.targettype in DLL_TARGETTYPES and self.targettype != TARGETTYPE_LIB:

            env.Command( self._target_resultable % ( "." + self.targettype ), [ temp_dll_path, self._target_resultable % ".def" ],
            [
                " ".join( [
                            'mwldsym2 -msgstyle gcc',
                            '-stdlib %EPOCROOT%epoc32/release/winscw/udeb/edll.lib -noentry',
                            '-shared -subsystem windows',
                            '-g %s' % " ".join( libs ),
                            '-o "%s"' % temp_dll_path,
                            '-f "%s"' % ( self._target_resultable % ".def" ),
                            '-implib "%s"' % ( self._target_resultable % ".lib" ),
                            '-addcommand "out:%s.%s"' % ( self.target, self.targettype ),
                            '-warnings off',
                            '-l %s' % " -l ".join( set( object_folders ) ),
                            '-search ' + objects,
                          ]
                        )
            ]
            )
        elif self.targettype == TARGETTYPE_EXE:
            env.Command( self._target_resultable % ".exe", temp_dll_path,
                [
                " ".join( [ 'mwldsym2',
                            '-msgstyle gcc',
                            '-stdlib %EPOCROOT%epoc32/release/winscw/udeb/eexe.lib',
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
    
        return build_prog
    
    def _handleHelp(self):
        if not self.help:
            return
        
        helpresult = SymbianHelp( self.help, self.uid3, env = self._env )
        #if COMPILER == COMPILER_WINSCW:
            #self._env.Install( join( FOLDER_EMULATOR_C, "resource", "help" ), helpresult[0] )#IGNORE:E1101
        
        ToPackage( self._env, self.package_drive_map, self.package,
                    join( "resource", "help" ),
                    helpresult[0] )
        #
        self.extra_depends.extend( helpresult )
        
    def _handleMMP(self):
        import mmp_parser
        p = mmp_parser.MMPParser( self.target )
        data = p.Parse()
        
        #pylint: disable-msg=W0201
        self.target = data["target"]
        self.targettype = data["targettype"]
        self.sources = data["source"]        
        self.includes = data["systeminclude"] + data["userinclude"]
        self.resources = data["resources"]
        self.libraries = data["library"]
        self.uid2 = data["uid"][0]
        self.uid3 = data["uid"][1]
        
        # Allow override in SConstruct
        if self.capabilities is None:
            self.capabilities = data["capability"]
        
        # Allow override in SConstruct
        if self.rssdefines is None:
            self.rssdefines = data["macro"][:]
        
        self.defines       = data["macro"][:]
        self.allowdlldata  = data["epocallowdlldata"]
        self.epocstacksize = data["epocstacksize"]
        #pylint: enable-msg=W0201
        
    def Process(self):
        
        # Skip processing to speed up help message
        if HELP_ENABLED: return
        
        if self.target.lower().endswith( ".mmp" ):
            self._handleMMP()
           
        if self.includes is None:
            self.includes = []
        
        if self.defines is None:
            self.defines = []
        
        self.defines = self.defines[:] # Copy
        
        if self.extra_depends is None:
            self.extra_depends = []    
            
        if self.sysincludes is None:
            self.sysincludes = []
            
        self.sysincludes.extend( SYSTEM_INCLUDES )
        
        if self.help:
        # Adds the .hrh file to include path
            self.includes.append( os.path.dirname( self.help ) )
        
        if self.libraries is None:
            self.libraries = []
            
        if CMD_LINE_LIBS is not None:
            self.libraries.extend( CMD_LINE_LIBS )
        
        if self.capabilities is None:
            self.capabilities = FREE_CAPS
        
        # Handle UIDs
        if self.uid2 is None:
            if self.targettype == TARGETTYPE_EXE:
                self.uid2 = "0x100039ce"
            else:
                self.uid2 = "0x0"
        
        if self.uid3 is None:
            self.uid3 = "0x0"
        elif type(self.uid3) != str:             
            self.uid3 = hex(self.uid3)[:-1]
        
        if not self.sid:
            self.sid = self.uid3                            
        elif type(self.sid) != str:
            self.sid = hex(self.sid)[:-1]
        
        # Add macros to ease changing application UID
        self.uiddefines = [
            "__UID3__=%s" % self.uid3
        ]
        
        self.defines.extend( self.uiddefines )
        
        if self.rssdefines is None:
            self.rssdefines = []
        self.rssdefines.append( r'LANGUAGE_SC' ) 
        self.rssdefines.extend( self.uiddefines )
        
        # Check if this Symbian component is enabled
        if not self._isComponentEnabled():            
            return None                    
    
        # ???: SCons is able to compile sources with self.output_folder 
        #      but not able to detect if the files have changed without
        #      explicit dependency!! Without self.output_folder the resulting object
        #      files are stored in the same folder as sources causing cross compiling
        #      to fail.
        # Seems to work again without. What is going on here? Updated scons 1.1?
        #self.extra_depends.extend( self.sources )
        self.origsources = self.sources[:]
        self.sources = [ join( self.output_folder, x ) for x in self.sources ]
        
        # This is often needed
        FOLDER_TARGET_TUPLE = ( self.output_folder, self.target )    
        Mkdir( self.output_folder )
        
        # Target resultable template. Just give extension of the file
        self._target_resultable = "%s/%s" % FOLDER_TARGET_TUPLE + "%s"
        
        # Copy the modified keywords from self ignoring private 
        kwargs = {}
        for x in dir(self):
            if x.startswith("_"):
                continue
            kwargs[x] = getattr( self, x )
                    
        self._env = _create_environment( **kwargs )
        
        # Don't duplicate to ease use of IDE(Carbide)
        self._env.BuildDir( self.output_folder, ".", duplicate = 0 )
        
        #------------------------------------------------------- Generate help files
        self._handleHelp()
    
        #-------------------------------------------------------------- Create icons
        self._handleIcons()                
        
        #---------------------------------------------------- Convert resource files 
        self._convertResources()
        
        # To be copied to /epoc32/release/WINSCW/UDEB/
        self.output_libpath = None
    
        build_prog = None
        #---------------------------------------------------------- Build using GCCE
        if COMPILER == COMPILER_GCCE:
            build_prog = self._handleGCCEBuild()
        #-------------------------------------------------------- Build using WINSCW
        else:
            build_prog = self._handleWINSCWBuild()
        
        
        self._env.Depends( build_prog, self.converted_icons )
        self._env.Depends( build_prog, self.converted_resources )
        self._env.Depends( build_prog, self.resource_headers )

        for dep in self.extra_depends:
            self._env.Depends( self.sources, dep )
            self._env.Depends( build_prog, dep )
        
        #-------------------------------------------------------------- Copy results
        installed = self._copyResultBinary()
        
        #---------------------------------------------------------------- Export MMP
        if self.mmpexport is not None:
            exporter = mmp_parser.MMPExporter( self.mmpexport )
            data = exporter.MMPData
            
            data.TARGET = self.target
            #import pdb;pdb.set_trace()
            data.TARGETTYPE = self.targettype
            #import pdb;pdb.set_trace()
            defines = self.defines[:] + EXTRA_DEFINES
            #for d in STANDARD_DEFINES:
            #    if d in defines:
            #        defines.remove(d)
            if hasattr( self, "epocstacksize" ):
                data.EPOCSTACKSIZE = self.epocstacksize
            if hasattr( self, "epocheapsize" ):
                data.EPOCHEAPSIZE  = self.epocheapsize
                
            if self.resources:
                data.RESOURCE = self.resources[:]
                        
            data.MACRO   = defines
            data.SOURCE  = self.origsources[:]
            data.LIBRARY = self.libraries[:]
            data.UID2    = self.uid2.replace("L","")
            data.UID3    = self.uid3.replace("L","")
            data.CAPABILITY = self.capabilities[:]
            data.USERINCLUDE.extend( self.includes )
            data.SYSTEMINCLUDE = self.sysincludes[:]
            #import pdb;pdb.set_trace()
            exporter.Export()
            exporter.Save()
            
            print( "Info: MMP exported '%s'" % self.mmpexport )
            
        if self.package is not None and self.package != "" and self.targettype != TARGETTYPE_LIB:
            # package depends on the files anyway
            self._env.Depends( self.package, installed )
        
        # Extra cleaning
        # It is easy to leave stuff with old names lying around 
        # and those are never cleaned otherwise
        Clean( build_prog, self.output_folder )
        
        return build_prog