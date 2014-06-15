from clang import cindex
import functiondecomposition
import os
import gccparity

_PREFIX_KEYWORDS_TO_FUNCTIONS_TO_DISCARD = [ "static", "inline", "extern", "virtual" ]

class IterateAPI:
    def __init__( self ):
        pass

    def handleError( self, severity, location, spelling, ranges, fixits ):
        assert False, "Please override in deriving class"

    def structForwardDeclaration( self, name ): assert False, "Please override in deriving class"
    def enterStruct( self, name, inheritance, fullText ): assert False, "Please override in deriving class"
    def leaveStruct( self ): assert False, "Please override in deriving class"
    def enterClass( self, name, inheritance, fullText ): assert False, "Please override in deriving class"
    def leaveClass( self ): assert False, "Please override in deriving class"
    def variableDeclaration( self, name, text ): assert False, "Please override in deriving class"
    def typedef( self, name, text ): assert False, "Please override in deriving class"
    def union( self, name, text ): assert False, "Please override in deriving class"
    def enum( self, name, text ): assert False, "Please override in deriving class"
    def functionForwardDeclaration( self, decomposition ): assert False, "Please override in deriving class"
    def functionDefinition( self, decomposition ): assert False, "Please override in deriving class"
    def constructorDefinition( self, decomposition ): assert False, "Please override in deriving class"
    def method( self, decomposition ): assert False, "Please override in deriving class"
    def conversionFunction( self, conversionType, const ): assert False, "Please override in deriving class"
    def fieldDeclaration( self, name, text ): assert False, "Please override in deriving class"
    def enterNamespace( self, name ): assert False, "Please override in deriving class"
    def leaveNamespace( self ): assert False, "Please override in deriving class"
    def accessSpec( self, access ): assert False, "Please override in deriving class"
    def using( self, text ): assert False, "Please override in deriving class"

    def process( self, filename, includes = [], defines = [], preIncludes = [] ):
        index = cindex.Index.create()
        FORCE_CPLUSPLUS = [ "-x", "c++", "-std=gnu++11" ]
        preIncludeArgs = [ "-include", gccparity.emulateGCCInClangPreinclude ] + sum( [ [ "-include", p ] for p in preIncludes ], [] )
        includes = includes + gccparity.gccIncludePath()
        args = FORCE_CPLUSPLUS + preIncludeArgs + [ filename ] + [ '-I' + i for i in includes ] + [ '-D' + d for d in defines ]
        if 'VOODOO_DEBUG_PREPROCESS_OUTPUT_FILE' in os.environ:
            os.system( "clang -E %s > %s" % ( " ".join( args ), os.environ[ 'VOODOO_DEBUG_PREPROCESS_OUTPUT_FILE' ] ) )
        translationUnit = index.parse( path = None, args = args )
#translationUnit = index.parse( path = None, args = args, options = cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES )
        if not translationUnit:
            raise Exception( "Unable to load '%s'" % filename )
        for diagnostic in translationUnit.diagnostics:
            self.handleError(   severity = diagnostic.severity,
                                location = diagnostic.location,
                                spelling = diagnostic.spelling,
                                ranges = diagnostic.ranges,
                                fixits = diagnostic.fixits )
        for node in self.__relevantNodes( translationUnit, filename ):
            self.__iterateNode( node )

    def __relevantNodes( self, translationUnit, filename ):
        return [ node for node in translationUnit.cursor.get_children() if node.location.file.name == filename ]

    def __iterateNode( self, node ):
        if node.kind == cindex.CursorKind.STRUCT_DECL and not node.is_definition():
            self.structForwardDeclaration( name = node.spelling )
        elif node.kind == cindex.CursorKind.STRUCT_DECL and node.is_definition():
            self.enterStruct( name = node.spelling, inheritance = self.__classInheritance( node ),
                    fullText = self.__nodeText( node, removeEverythingAfterLastClosingBrace = True ) )
            for child in node.get_children():
                self.__iterateNode( child )
            self.leaveStruct()
        elif node.kind == cindex.CursorKind.CLASS_DECL and node.is_definition():
            self.enterClass( name = node.spelling, inheritance = self.__classInheritance( node ),
                    fullText = self.__nodeText( node, removeEverythingAfterLastClosingBrace = True ) )
            for child in node.get_children():
                self.__iterateNode( child )
            self.leaveClass()
        elif node.kind == cindex.CursorKind.UNEXPOSED_DECL: #extern "C"
            for child in node.get_children():
                self.__iterateNode( child )
        elif node.kind == cindex.CursorKind.VAR_DECL:
            self.variableDeclaration( name = node.spelling, text = self.__nodeText( node, removePrefixKeywords = [ 'static' ] ) )
        elif node.kind == cindex.CursorKind.FIELD_DECL:
            self.fieldDeclaration( name = node.spelling, text = self.__nodeText( node ) )
        elif node.kind == cindex.CursorKind.TYPEDEF_DECL:
            self.typedef( name = node.spelling, text = self.__nodeText( node, removeBraces = True ) )
        elif node.kind == cindex.CursorKind.ENUM_DECL:
            self.enum( name = node.spelling, text = self.__nodeText( node ) )
        elif node.kind == cindex.CursorKind.FUNCTION_DECL and not node.is_definition():
            children = self.__functionParameters( node )
            parameters = [ self.__parseParameter( children[ i ], lastParameter = i == len( children ) - 1 ) for i in xrange( len( children ) ) ]
            text = self.__nodeText( node, removeLastParenthesis = True, removePrefixKeywords = _PREFIX_KEYWORDS_TO_FUNCTIONS_TO_DISCARD,
                    removeSuffixKeywords = [ 'noexcept' ] )
            returnType = self.__removeSpaceInsensitive( text, node.spelling )
            decomposition = functiondecomposition.FunctionDecomposition(
                                                        name = node.spelling,
                                                        text = text,
                                                        parameters = parameters,
                                                        returnType = returnType,
                                                        static = True,
                                                        const = False )
            self.functionForwardDeclaration( decomposition = decomposition )
        elif node.kind == cindex.CursorKind.FUNCTION_DECL and node.is_definition():
            children = self.__functionParameters( node )
            parameters = [ self.__parseParameter( children[ i ], lastParameter = i == len( children ) - 1 ) for i in xrange( len( children ) ) ]
            text = self.__nodeText( node, removeBraces = True, removeLastParenthesis = True, removePrefixKeywords = _PREFIX_KEYWORDS_TO_FUNCTIONS_TO_DISCARD, removeOneNonPunctuationTokenFromTheEnd = True, removeSuffixKeywords = [ 'noexcept' ] )
            returnType = self.__removeSpaceInsensitive( text, node.spelling )
            decomposition = functiondecomposition.FunctionDecomposition(
                                                                name = node.spelling,
                                                                text = text,
                                                                parameters = parameters,
                                                                returnType = returnType,
                                                                static = True,
                                                                const = False )
            self.functionDefinition( decomposition = decomposition )
        elif node.kind == cindex.CursorKind.CONSTRUCTOR:
            children = self.__functionParameters( node )
            parameters = [ self.__parseParameter( children[ i ], lastParameter = i == len( children ) - 1 ) for i in xrange( len( children ) ) ]
            decomposition = functiondecomposition.FunctionDecomposition(
                                                                name = node.spelling,
                                                                text = node.spelling,
                                                                parameters = parameters,
                                                                returnType = None,
                                                                static = None,
                                                                const = False )
            self.constructorDefinition( decomposition = decomposition )
        elif node.kind == cindex.CursorKind.CXX_METHOD:
            children = self.__functionParameters( node )
            parameters = [ self.__parseParameter( children[ i ], lastParameter = i == len( children ) - 1 ) for i in xrange( len( children ) ) ]
            text = self.__nodeText( node, removeBraces = True, removeLastParenthesis = True, removePrefixKeywords = _PREFIX_KEYWORDS_TO_FUNCTIONS_TO_DISCARD, removeOneNonPunctuationTokenFromTheEnd = True, removeSuffixKeywords = [ 'const', 'override', 'noexcept' ] )
            returnType = self.__removeSpaceInsensitive( text, node.spelling )
            decomposition = functiondecomposition.FunctionDecomposition(
                                                                name = node.spelling,
                                                                text = node.spelling,
                                                                parameters = parameters,
                                                                returnType = returnType,
                                                                static = node.is_static_method(),
                                                                const = self.__isMethodConst( node ))
            self.method( decomposition = decomposition )
        elif node.kind == cindex.CursorKind.CONVERSION_FUNCTION:
            assert node.spelling.startswith( "operator" )
            conversionType = node.spelling[ len( "operator" ) : ].strip()
            self.conversionFunction( conversionType = conversionType, const = self.__isMethodConst( node ) )
        elif node.kind == cindex.CursorKind.DESTRUCTOR:
            pass
        elif node.kind == cindex.CursorKind.NAMESPACE:
            self.enterNamespace( name = node.spelling )
            for child in node.get_children():
                self.__iterateNode( child )
            self.leaveNamespace()
        elif node.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
            access = node.get_tokens().next().spelling
            self.accessSpec( access = access )
        elif node.kind == cindex.CursorKind.USING_DIRECTIVE:
            text = self.__nodeText( node )
            self.using( text = text )
        elif node.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
            pass
        elif node.kind == cindex.CursorKind.UNION_DECL:
            if node.spelling == '':
                return
            self.union( name = node.spelling, text = self.__nodeText( node ) )
        else:
            try: nodeText = self.__nodeText( node )
            except Exception as e: nodeText = "Exception (%s)" % str( e )
            raise Exception( "Voodoo does not recognize the following node:\n%s\nNode text:\n%s" % ( self.__traceNode( node ), nodeText ) )

    def __classInheritance( self, node ):
        inheritance = []
        try:
            for child in node.get_children():
                if child.kind != cindex.CursorKind.CXX_BASE_SPECIFIER:
                    break
                protection = child.get_tokens().next().spelling
                if protection not in [ 'public', 'protected' ]:
                    continue
                inheritance.append( ( protection, self.__fullNamespaceType( child.type.get_declaration() ) ) )
        except StopIteration:
            pass
        return inheritance

    def __functionParameters( self, node ):
        return [ child for child in node.get_children() if child.kind == cindex.CursorKind.PARM_DECL ]

    def __parseParameter( self, node, lastParameter ):
        terminator = ')' if lastParameter else ','
        return dict( name = node.spelling, text = self.__nodeText( node, terminatorCharacter = terminator ) )

    def __textualType( self, type ):
        if type.kind == cindex.TypeKind.VOID:
            returnType = "void"
        elif type.kind == cindex.TypeKind.INT:
            returnType = "int"
        elif type.kind == cindex.TypeKind.CHAR_S:
            returnType = "char"
        elif type.kind == cindex.TypeKind.POINTER:
            returnType = self.__textualType( type.get_pointee() ) + " *"
        elif type.kind == cindex.TypeKind.BOOL:
            returnType = "bool"
        elif type.kind == cindex.TypeKind.CHAR_U:
            returnType = "unsigned char"
        elif type.kind == cindex.TypeKind.UCHAR:
            returnType = "unsigned char"
        elif type.kind == cindex.TypeKind.SHORT:
            returnType = "short"
        elif type.kind == cindex.TypeKind.USHORT:
            returnType = "unsigned short"
        elif type.kind == cindex.TypeKind.UINT:
            returnType = "unsigned int"
        elif type.kind == cindex.TypeKind.LONG:
            returnType = "long"
        elif type.kind == cindex.TypeKind.ULONG:
            returnType = "unsigned long"
        elif type.kind == cindex.TypeKind.LONGLONG:
            returnType = "long long"
        elif type.kind == cindex.TypeKind.ULONGLONG:
            returnType = "unsigned long long"
        elif type.kind == cindex.TypeKind.FLOAT:
            returnType = "float"
        elif type.kind == cindex.TypeKind.DOUBLE:
            returnType = "double"
        elif type.kind == cindex.TypeKind.LONGDOUBLE:
            returnType = "long double"
        elif type.kind == cindex.TypeKind.TYPEDEF:
            declaration = type.get_declaration()
            returnType = declaration.spelling
        elif type.kind == cindex.TypeKind.UNEXPOSED:
            declaration = type.get_declaration()
            returnType = self.__fullNamespaceType( declaration )
        elif type.kind == cindex.TypeKind.LVALUEREFERENCE:
            returnType = self.__fullNamespaceType( type.get_pointee().get_declaration() )
            returnType += " &"
            if type.get_pointee().is_const_qualified():
                returnType = "const " + returnType
        elif type.kind == cindex.TypeKind.RECORD:
            returnType = self.__fullNamespaceType( type.get_declaration() )
        else:
            assert False, "Unknown typekind: '%s'" % type.kind
        if type.is_const_qualified():
            if type.kind == cindex.TypeKind.POINTER:
                returnType = returnType + " const"
            else:
                returnType = "const " + returnType
        return returnType

    def __traceNode( self, node, depth = 0 ):
        indent = depth * "  "
        output = "%sNode:\n" % indent
        output += "%s kind: '%s', spelling: '%s'\n" % ( indent, node.kind, node.spelling )
        output += "%s location: '%s', extentStart: '%s', extentEnd: '%s'\n" % ( indent, node.location, node.extent.start, node.extent.end )
        output += "%s is definition: '%s', children '%d'\n" % ( indent, node.is_definition(), len( list( node.get_children() ) ) )
        for child in node.get_children():
            output += self.__traceNode( child, depth + 1 )
        return output

    def __removeParenthesisFromTokenList( self, tokens, opening = '(', closing = ')' ):
        if tokens[ -1 ].spelling != closing:
            return tokens
        del tokens[ -1 ]
        parenDepth = 1
        while parenDepth > 0:
            if tokens[ -1 ].spelling == closing:
                parenDepth += 1
            elif tokens[ -1 ].spelling == opening:
                parenDepth -= 1
            del tokens[ -1 ]
        return tokens

    def __pointeeIsUnexposedStructDefinition( self, pointee ):
        tokens = list( pointee.get_declaration().get_tokens() )
        return tokens[ -1 ].spelling == ';' and tokens[ -2 ].spelling == '}'

    def __nodeText( self,
                    node,
                    terminatorCharacter = ';',
                    removeLastParenthesis = False,
                    removeBraces = False,
                    removePrefixKeywords = [],
                    removeSuffixKeywords = [],
                    removeEverythingAfterLastClosingBrace = False,
                    removeOneNonPunctuationTokenFromTheEnd = False ):
        tokens = [ t for t in node.get_tokens()
                    if t.kind != cindex.TokenKind.COMMENT and
                        t.spelling != '#' ]
        while len( tokens ) > 0 and tokens[ 0 ].spelling in removePrefixKeywords:
            del tokens[ 0 ]
        if removeBraces:
            if len( [ i for i in xrange( len( tokens ) ) if tokens[ i ].spelling == "{" ] ) > 0:
                firstLocation = [ i for i in xrange( len( tokens ) ) if tokens[ i ].spelling == "{" ][ 0 ]
                lastLocation = [ i for i in xrange( len( tokens ) ) if tokens[ i ].spelling == "}" ][ -1 ]
                del tokens[ firstLocation : lastLocation + 1 ]
        if len( tokens ) > 0 and tokens[ -1 ].spelling == terminatorCharacter:
            del tokens[ -1 ]
        if removeOneNonPunctuationTokenFromTheEnd:
            if len( tokens ) > 0 and tokens[ -1 ].kind != cindex.TokenKind.PUNCTUATION:
                if len( tokens ) >= 2 and tokens[ -2 ].spelling == '=' and \
                        tokens[ -1 ].spelling in [ '0' ]:
                    tokens.pop()
                tokens.pop()
            elif len( tokens ) > 0 and tokens[ -1 ].spelling == '=':
                tokens.pop()
        while len( tokens ) > 0 and tokens[ -1 ].spelling in removeSuffixKeywords:
            tokens.pop()
        if len( tokens ) > 0 and removeLastParenthesis:
            tokens = self.__removeParenthesisFromTokenList( tokens )
        if removeEverythingAfterLastClosingBrace:
            while len( [ i for i in xrange( len( tokens ) ) if tokens[ i ].spelling == '}' ] ) > 0 and \
                    tokens[ -1 ].spelling != '}':
                tokens.pop()
        return " ".join( [ token.spelling for token in tokens ] )

    def __fullNamespaceType( self, node ):
        text = node.spelling
        ancestor = node.semantic_parent
        while ancestor and ancestor.spelling:
            text = ancestor.spelling + "::" + text
            ancestor = ancestor.semantic_parent
        return text

    def __isMethodConst( self, node ):
        typeQualifier = node.get_usr().split( "#" )[ -1 ]
        if not typeQualifier.isdigit():
            return False
        return ( int( typeQualifier ) & 0x01 ) != 0

    def __removeSpaceInsensitive( self, string, suffix ):
        spacelessSuffix = suffix.replace( ' ', '' )
        spaceSeperated = string.split( " " )
        removed = ""
        while len( removed ) < len( spacelessSuffix ):
            removed = spaceSeperated.pop() + removed
        assert removed == spacelessSuffix, "String '%s' does not end with '%s'" % ( string, suffix )
        return " ".join( spaceSeperated ).strip()
