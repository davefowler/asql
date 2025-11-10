"""ASQL parser - converts ASQL text to AST."""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class NodeType(Enum):
    """AST node types."""
    QUERY = "query"
    FROM = "from"
    WHERE = "where"
    IF = "if"
    GROUP_BY = "group_by"
    SELECT = "select"
    PROJECT = "project"
    SORT = "sort"
    TAKE = "take"
    DERIVE = "derive"
    JOIN = "join"
    SET = "set"
    LET = "let"
    EXPRESSION = "expression"
    AGGREGATE = "aggregate"
    FUNCTION_CALL = "function_call"
    IDENTIFIER = "identifier"
    LITERAL = "literal"
    BINARY_OP = "binary_op"
    UNARY_OP = "unary_op"


@dataclass
class ASTNode:
    """Base AST node."""
    node_type: NodeType
    value: Any = None
    children: List["ASTNode"] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class Parser:
    """ASQL parser."""
    
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.tokens = []
        self._tokenize()
    
    def _tokenize(self) -> None:
        """Tokenize the input text."""
        import re
        
        # Token patterns
        patterns = [
            (r'\s+', None),  # Whitespace (skip)
            (r'--.*', None),  # Single-line comments
            (r'/\*.*?\*/', None),  # Multi-line comments
            (r'==', 'EQ'),
            (r'!=', 'NE'),
            (r'<=', 'LE'),
            (r'>=', 'GE'),
            (r'<', 'LT'),
            (r'>', 'GT'),
            (r'&&', 'AND'),
            (r'\|\|', 'OR'),
            (r'\+', 'PLUS'),
            (r'-', 'MINUS'),
            (r'\*', 'MULT'),
            (r'/', 'DIV'),
            (r'%', 'MOD'),
            (r'\(', 'LPAREN'),
            (r'\)', 'RPAREN'),
            (r'\{', 'LBRACE'),
            (r'\}', 'RBRACE'),
            (r'\[', 'LBRACKET'),
            (r'\]', 'RBRACKET'),
            (r',', 'COMMA'),
            (r'\.', 'DOT'),
            (r'#', 'HASH'),
            (r'\|', 'PIPE'),
            (r'@(\d{4}-\d{2}-\d{2})', 'DATE'),  # @2025-01-10
            (r'"([^"]*)"', 'STRING'),
            (r"'([^']*)'", 'STRING'),
            (r'\d+\.\d+', 'FLOAT'),
            (r'\d+', 'INT'),
            (r'[a-zA-Z_][a-zA-Z0-9_]*', 'IDENTIFIER'),
        ]
        
        compiled_patterns = [(re.compile(p), t) for p, t in patterns]
        
        while self.pos < len(self.text):
            matched = False
            for pattern, token_type in compiled_patterns:
                match = pattern.match(self.text, self.pos)
                if match:
                    if token_type:
                        value = match.group(0)
                        if token_type == 'DATE':
                            value = match.group(1)  # Extract date part
                        elif token_type == 'STRING':
                            value = match.group(1)  # Extract string content
                        self.tokens.append((token_type, value, self.pos))
                    self.pos = match.end()
                    matched = True
                    break
            
            if not matched:
                raise SyntaxError(f"Unexpected character at position {self.pos}: {self.text[self.pos]}")
    
    def parse(self) -> ASTNode:
        """Parse tokens into AST."""
        if not self.tokens:
            raise SyntaxError("Empty input")
        
        # Parse query (can start with SET/LET or FROM)
        if self._peek() == 'SET':
            return self._parse_set()
        elif self._peek() == 'LET':
            return self._parse_let()
        else:
            return self._parse_query()
    
    def _parse_query(self) -> ASTNode:
        """Parse a query starting with FROM."""
        if self._peek() != 'FROM':
            raise SyntaxError(f"Expected FROM, got {self._peek()}")
        
        self._consume('FROM')
        table = self._parse_identifier()
        
        query = ASTNode(NodeType.QUERY, children=[
            ASTNode(NodeType.FROM, value=table.value)
        ])
        
        # Parse pipeline operators
        while self.pos < len(self.tokens):
            op = self._parse_pipeline_op()
            if op:
                query.children.append(op)
            else:
                break
        
        return query
    
    def _parse_pipeline_op(self) -> Optional[ASTNode]:
        """Parse a pipeline operator."""
        if self.pos >= len(self.tokens):
            return None
        
        token_type = self._peek()
        
        if token_type == 'WHERE':
            return self._parse_where()
        elif token_type == 'IF':
            return self._parse_if()
        elif token_type == 'GROUP':
            return self._parse_group_by()
        elif token_type == 'SELECT' or token_type == 'PROJECT':
            return self._parse_select()
        elif token_type == 'SORT':
            return self._parse_sort()
        elif token_type == 'TAKE':
            return self._parse_take()
        elif token_type == 'DERIVE':
            return self._parse_derive()
        elif token_type == 'JOIN':
            return self._parse_join()
        elif token_type == 'PIPE':
            self._consume('PIPE')
            return self._parse_pipeline_op()
        else:
            return None
    
    def _parse_where(self) -> ASTNode:
        """Parse WHERE clause."""
        self._consume('WHERE')
        expr = self._parse_expression()
        return ASTNode(NodeType.WHERE, children=[expr])
    
    def _parse_if(self) -> ASTNode:
        """Parse IF clause (alias for WHERE)."""
        self._consume('IF')
        expr = self._parse_expression()
        return ASTNode(NodeType.IF, children=[expr])
    
    def _parse_group_by(self) -> ASTNode:
        """Parse GROUP BY clause."""
        self._consume('GROUP')
        self._consume('BY')
        
        # Parse grouping columns
        group_cols = []
        while True:
            col = self._parse_expression()
            group_cols.append(col)
            if self._peek() != 'COMMA':
                break
            self._consume('COMMA')
        
        # Parse aggregates in parentheses
        aggregates = []
        if self._peek() == 'LPAREN':
            self._consume('LPAREN')
            while self._peek() != 'RPAREN':
                agg = self._parse_aggregate()
                aggregates.append(agg)
                if self._peek() == 'COMMA':
                    self._consume('COMMA')
                elif self._peek() != 'RPAREN':
                    break
            self._consume('RPAREN')
        
        return ASTNode(NodeType.GROUP_BY, value={'columns': group_cols, 'aggregates': aggregates})
    
    def _parse_aggregate(self) -> ASTNode:
        """Parse an aggregate expression."""
        # Check for # syntax
        if self._peek() == 'HASH':
            self._consume('HASH')
            expr = None
            if self._peek() == 'LPAREN':
                self._consume('LPAREN')
                if self._peek() != 'RPAREN':
                    expr = self._parse_expression()
                self._consume('RPAREN')
            
            alias = None
            if self._peek() == 'AS':
                self._consume('AS')
                alias = self._parse_identifier()
            
            return ASTNode(NodeType.AGGREGATE, value={
                'function': 'count',
                'distinct': False,
                'expression': expr,
                'alias': alias.value if alias else None
            })
        
        # Parse function call or natural language aggregate
        func_name = self._parse_identifier()
        func_name_lower = func_name.value.lower()
        
        # Check if it's a natural language aggregate
        if func_name_lower in ('sum', 'total', 'avg', 'average', 'min', 'max', 'count'):
            # Check for "of" keyword
            if self._peek() == 'IDENTIFIER' and self._peek_value().lower() == 'of':
                self._consume('IDENTIFIER')
            
            expr = self._parse_expression()
            
            alias = None
            if self._peek() == 'AS':
                self._consume('AS')
                alias = self._parse_identifier()
            
            # Normalize function names
            if func_name_lower == 'total':
                func_name_lower = 'sum'
            elif func_name_lower == 'average':
                func_name_lower = 'avg'
            
            return ASTNode(NodeType.AGGREGATE, value={
                'function': func_name_lower,
                'distinct': False,
                'expression': expr,
                'alias': alias.value if alias else None
            })
        
        # Regular function call syntax: count(expr), sum(expr), etc.
        if self._peek() == 'LPAREN':
            self._consume('LPAREN')
            distinct = False
            if self._peek() == 'IDENTIFIER' and self._peek_value().lower() == 'distinct':
                self._consume('IDENTIFIER')
                distinct = True
            
            expr = self._parse_expression() if self._peek() != 'RPAREN' else None
            self._consume('RPAREN')
            
            alias = None
            if self._peek() == 'AS':
                self._consume('AS')
                alias = self._parse_identifier()
            
            return ASTNode(NodeType.AGGREGATE, value={
                'function': func_name_lower,
                'distinct': distinct,
                'expression': expr,
                'alias': alias.value if alias else None
            })
        
        raise SyntaxError(f"Unexpected token in aggregate: {self._peek()}")
    
    def _parse_select(self) -> ASTNode:
        """Parse SELECT/PROJECT clause."""
        token_type = self._peek()
        self._consume(token_type)
        
        columns = []
        if self._peek() == 'MULT':
            self._consume('MULT')
            columns.append(ASTNode(NodeType.IDENTIFIER, value='*'))
        else:
            while True:
                col = self._parse_expression()
                columns.append(col)
                if self._peek() != 'COMMA':
                    break
                self._consume('COMMA')
        
        return ASTNode(NodeType.SELECT, children=columns)
    
    def _parse_sort(self) -> ASTNode:
        """Parse SORT clause."""
        self._consume('SORT')
        
        columns = []
        while True:
            desc = False
            if self._peek() == 'MINUS':
                self._consume('MINUS')
                desc = True
            
            col = self._parse_expression()
            columns.append(ASTNode(NodeType.EXPRESSION, value={'column': col, 'desc': desc}))
            
            if self._peek() != 'MINUS' and self._peek() != 'IDENTIFIER':
                break
        
        return ASTNode(NodeType.SORT, children=columns)
    
    def _parse_take(self) -> ASTNode:
        """Parse TAKE clause."""
        self._consume('TAKE')
        num = self._parse_literal()
        return ASTNode(NodeType.TAKE, value=num.value)
    
    def _parse_derive(self) -> ASTNode:
        """Parse DERIVE clause."""
        self._consume('DERIVE')
        
        # Parse: derive col as expr
        col = self._parse_identifier()
        self._consume('AS')
        expr = self._parse_expression()
        
        return ASTNode(NodeType.DERIVE, value={'column': col.value, 'expression': expr})
    
    def _parse_join(self) -> ASTNode:
        """Parse JOIN clause."""
        self._consume('JOIN')
        table = self._parse_identifier()
        
        condition = None
        if self._peek() == 'ON':
            self._consume('ON')
            condition = self._parse_expression()
        
        return ASTNode(NodeType.JOIN, value={'table': table.value, 'condition': condition})
    
    def _parse_set(self) -> ASTNode:
        """Parse SET variable."""
        self._consume('SET')
        var_name = self._parse_identifier()
        self._consume('EQ')
        query = self._parse_query()
        return ASTNode(NodeType.SET, value={'name': var_name.value, 'query': query})
    
    def _parse_let(self) -> ASTNode:
        """Parse LET variable."""
        self._consume('LET')
        var_name = self._parse_identifier()
        self._consume('EQ')
        query = self._parse_query()
        return ASTNode(NodeType.LET, value={'name': var_name.value, 'query': query})
    
    def _parse_expression(self) -> ASTNode:
        """Parse an expression."""
        return self._parse_logical_or()
    
    def _parse_logical_or(self) -> ASTNode:
        """Parse logical OR expression."""
        left = self._parse_logical_and()
        
        while self._peek() == 'OR' or (self._peek() == 'IDENTIFIER' and self._peek_value().lower() == 'or'):
            if self._peek() == 'OR':
                self._consume('OR')
            else:
                self._consume('IDENTIFIER')
            right = self._parse_logical_and()
            left = ASTNode(NodeType.BINARY_OP, value={'op': 'or', 'left': left, 'right': right})
        
        return left
    
    def _parse_logical_and(self) -> ASTNode:
        """Parse logical AND expression."""
        left = self._parse_comparison()
        
        while self._peek() == 'AND' or (self._peek() == 'IDENTIFIER' and self._peek_value().lower() == 'and'):
            if self._peek() == 'AND':
                self._consume('AND')
            else:
                self._consume('IDENTIFIER')
            right = self._parse_comparison()
            left = ASTNode(NodeType.BINARY_OP, value={'op': 'and', 'left': left, 'right': right})
        
        return left
    
    def _parse_comparison(self) -> ASTNode:
        """Parse comparison expression."""
        left = self._parse_additive()
        
        if self._peek() in ('EQ', 'NE', 'LT', 'LE', 'GT', 'GE'):
            op_token = self._peek()
            self._consume(op_token)
            right = self._parse_additive()
            
            op_map = {
                'EQ': '==',
                'NE': '!=',
                'LT': '<',
                'LE': '<=',
                'GT': '>',
                'GE': '>=',
            }
            return ASTNode(NodeType.BINARY_OP, value={'op': op_map[op_token], 'left': left, 'right': right})
        
        # Check for "is", "is not", "in", "not in"
        if self._peek() == 'IDENTIFIER':
            ident = self._peek_value().lower()
            if ident == 'is':
                self._consume('IDENTIFIER')
                if self._peek() == 'IDENTIFIER' and self._peek_value().lower() == 'not':
                    self._consume('IDENTIFIER')
                    right = self._parse_additive()
                    return ASTNode(NodeType.BINARY_OP, value={'op': 'is not', 'left': left, 'right': right})
                else:
                    right = self._parse_additive()
                    return ASTNode(NodeType.BINARY_OP, value={'op': 'is', 'left': left, 'right': right})
            elif ident == 'in':
                self._consume('IDENTIFIER')
                right = self._parse_additive()
                return ASTNode(NodeType.BINARY_OP, value={'op': 'in', 'left': left, 'right': right})
            elif ident == 'not':
                self._consume('IDENTIFIER')
                if self._peek() == 'IDENTIFIER' and self._peek_value().lower() == 'in':
                    self._consume('IDENTIFIER')
                    right = self._parse_additive()
                    return ASTNode(NodeType.BINARY_OP, value={'op': 'not in', 'left': left, 'right': right})
        
        return left
    
    def _parse_additive(self) -> ASTNode:
        """Parse additive expression."""
        left = self._parse_multiplicative()
        
        while self._peek() in ('PLUS', 'MINUS'):
            op_token = self._peek()
            self._consume(op_token)
            right = self._parse_multiplicative()
            op = '+' if op_token == 'PLUS' else '-'
            left = ASTNode(NodeType.BINARY_OP, value={'op': op, 'left': left, 'right': right})
        
        return left
    
    def _parse_multiplicative(self) -> ASTNode:
        """Parse multiplicative expression."""
        left = self._parse_unary()
        
        while self._peek() in ('MULT', 'DIV', 'MOD'):
            op_token = self._peek()
            self._consume(op_token)
            right = self._parse_unary()
            op_map = {'MULT': '*', 'DIV': '/', 'MOD': '%'}
            left = ASTNode(NodeType.BINARY_OP, value={'op': op_map[op_token], 'left': left, 'right': right})
        
        return left
    
    def _parse_unary(self) -> ASTNode:
        """Parse unary expression."""
        if self._peek() == 'MINUS':
            self._consume('MINUS')
            expr = self._parse_unary()
            return ASTNode(NodeType.UNARY_OP, value={'op': '-', 'operand': expr})
        elif self._peek() == 'NOT' or (self._peek() == 'IDENTIFIER' and self._peek_value().lower() == 'not'):
            if self._peek() == 'NOT':
                self._consume('NOT')
            else:
                self._consume('IDENTIFIER')
            expr = self._parse_unary()
            return ASTNode(NodeType.UNARY_OP, value={'op': 'not', 'operand': expr})
        
        return self._parse_primary()
    
    def _parse_primary(self) -> ASTNode:
        """Parse primary expression."""
        if self._peek() == 'LPAREN':
            self._consume('LPAREN')
            expr = self._parse_expression()
            self._consume('RPAREN')
            return expr
        elif self._peek() in ('INT', 'FLOAT', 'STRING', 'DATE'):
            return self._parse_literal()
        elif self._peek() == 'IDENTIFIER':
            ident = self._parse_identifier()
            
            # Check for function call
            if self._peek() == 'LPAREN':
                return self._parse_function_call(ident)
            
            # Check for dot notation (table.column)
            if self._peek() == 'DOT':
                self._consume('DOT')
                col = self._parse_identifier()
                return ASTNode(NodeType.EXPRESSION, value={
                    'type': 'column',
                    'table': ident.value,
                    'column': col.value
                })
            
            return ASTNode(NodeType.IDENTIFIER, value=ident.value)
        else:
            raise SyntaxError(f"Unexpected token in expression: {self._peek()}")
    
    def _parse_function_call(self, func_name: ASTNode) -> ASTNode:
        """Parse function call."""
        self._consume('LPAREN')
        args = []
        if self._peek() != 'RPAREN':
            args.append(self._parse_expression())
            while self._peek() == 'COMMA':
                self._consume('COMMA')
                args.append(self._parse_expression())
        self._consume('RPAREN')
        
        return ASTNode(NodeType.FUNCTION_CALL, value={'name': func_name.value, 'args': args})
    
    def _parse_identifier(self) -> ASTNode:
        """Parse identifier."""
        if self._peek() != 'IDENTIFIER':
            raise SyntaxError(f"Expected identifier, got {self._peek()}")
        token_type, value, _ = self.tokens[self.pos]
        self.pos += 1
        return ASTNode(NodeType.IDENTIFIER, value=value)
    
    def _parse_literal(self) -> ASTNode:
        """Parse literal value."""
        token_type = self._peek()
        if token_type not in ('INT', 'FLOAT', 'STRING', 'DATE'):
            raise SyntaxError(f"Expected literal, got {token_type}")
        
        _, value, _ = self.tokens[self.pos]
        self.pos += 1
        
        if token_type == 'INT':
            value = int(value)
        elif token_type == 'FLOAT':
            value = float(value)
        elif token_type == 'DATE':
            value = f"DATE '{value}'"
        
        return ASTNode(NodeType.LITERAL, value=value)
    
    def _peek(self) -> Optional[str]:
        """Peek at next token type."""
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos][0]
    
    def _peek_value(self) -> Optional[str]:
        """Peek at next token value."""
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos][1]
    
    def _consume(self, expected: str) -> None:
        """Consume expected token."""
        if self._peek() != expected:
            raise SyntaxError(f"Expected {expected}, got {self._peek()}")
        self.pos += 1

