from grizzly.dataframes.frame import Table, Projection, Filter, Join, Grouping, DataFrame
from grizzly.expression import ColRef, Expr

from grizzly.generator import GrizzlyGenerator

import random
import string

class Query:

  def __init__(self, groupagg = None):
    self.filters = []
    self.projections = None
    self.doDistinct = False
    self.table = None
    self.groupcols = []
    self.groupagg = groupagg
    self.joins = []

  def _reset(self):
    self.filters = []
    self.projections = None
    self.doDistinct = False
    self.table = None
    self.groupcols = []
    self.groupagg = None
    self.joins = []

  def _doExprToSQL(self, expr):
    exprSQL = ""
    # right hand side is a string constant
    if isinstance(expr, str):
      exprSQL = f"'{expr}'"
    # right hand side is a dataframe (i.e. subquery)
    elif isinstance(expr, DataFrame): 
      # if right hand side is a DataFrame, we need to create code first 
      subQry = Query()
      exprSQL = subQry._buildFrom(expr)

    elif isinstance(expr, ColRef):
      exprSQL = str(expr)

    elif isinstance(expr, Expr):
      l = self._doExprToSQL(expr.left)
      r = self._doExprToSQL(expr.right)

      exprSQL = f"{l} {expr.opStr} {r}"
    # right hand side is some constant (other than string), e.g. number
    else:
      exprSQL = str(expr)

    return exprSQL

  def _exprToSQL(self, expr):
    leftExpr = self._doExprToSQL(expr.left)
    rightExpr = self._doExprToSQL(expr.right)

    return f"{leftExpr} {expr.opStr} {rightExpr}"

  def _buildFrom(self,df):

    curr = df
    while curr is not None:

      if isinstance(curr,Table):
        self.table = f"{curr.table} {curr.alias}"

      elif isinstance(curr,Projection):
        if curr.attrs:
          prefixed = [str(attr) for attr in curr.attrs]
          if not self.projections:
            self.projections = prefixed
          else:
            set(self.projections).intersection(set(prefixed))
        

        if curr.doDistinct:
          self.doDistinct = True

      elif isinstance(curr,Filter):
        exprStr = self._exprToSQL(curr.expr)
        self.filters.append(exprStr)

      elif isinstance(curr, Join):
        # rtVar = DataFrame._incrAndGetTupleVar()
        

        if isinstance(curr.right, Table):
          rightSQL = curr.right.table
          rtVar = curr.right.alias
        else:
          subQry = Query()
          rightSQL = f"({subQry._buildFrom(curr.right)})"
          rtVar = GrizzlyGenerator._incrAndGetTupleVar()
          # curr.right.alias = rtVar
          curr.right.setAlias(rtVar)

        if isinstance(curr.on, Expr):
          onSQL = self._exprToSQL(curr.on)
        else:
          onSQL = f"{curr.alias}.{curr.on[0]} {curr.comp} {rtVar}.{curr.on[1]}"
        
        joinSQL = f"{curr.how} JOIN {rightSQL} {rtVar} ON {onSQL}"
        self.joins.append(joinSQL)

      elif isinstance(curr, Grouping):
        self.groupcols = [str(attr) for attr in curr.groupCols]

      if curr.parents is None:
        curr = None
      else:
        curr = curr.parents[0]

    joins = ""
    while self.joins:
      joins += " "+self.joins.pop()
    
    projs = "*"
    if self.projections:
      if self.groupcols and not self.projections.issubset(self.groupcols):
        raise ValueError("Projection list must be subset of group columns")

      projs = ', '.join(self.projections) 

    grouping = ""
    if self.groupcols:
      theColRefs = ", ".join([str(e) for e in self.groupcols])
      grouping += f" GROUP BY {theColRefs}"

      if projs == "*":
        projs = theColRefs

    if self.groupagg is not None:
      if projs == "*":
        projs = self.groupagg
      else:
        projs = projs + "," +self.groupagg

    if self.doDistinct:
      projs = "distinct " + projs

    where = ""
    if len(self.filters) > 0:
      exprs = " AND ".join([str(e) for e in self.filters])
      where += f" WHERE {exprs}"

    qrySoFar = f"SELECT {projs} FROM {self.table}{joins}{where}{grouping}"
    return qrySoFar

class SQLGenerator:

  def generate(self, df, aggFunc = None):
    qry = Query(aggFunc)
    return qry._buildFrom(df)
