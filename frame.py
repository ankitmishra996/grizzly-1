from sqlops import From, Filter, Projection, Grouping, Join
from column import Expr, Eq, Ne, Gt, Ge, Lt, Le, And, Or
from connection import Connection
import query


class DataFrame2(object):

  def __init__(self, columns, op):
    self.op = op
    self.columns = columns


#####################################################
### relational ops

  def filter(self, expr):
    self.op = Filter(expr, self.op)
    return self

  def project(self, attrs):
    # print(self)
    # print(attrs)
    # print("---------")
    op = Projection(attrs, self.op)
    newColumns = attrs #[col for col in self.columns if col.name in attrs]

    return DataFrame2(newColumns, op)

  def distinct(self):
    newOp = Projection(None, self.op, distinct = True)
    return DataFrame2(self.columns, newOp)

  def join(self, other, on, how, comp = "="):
    self.op = Join(other, on, how, comp, self.op)
    return DataFrame2(self.columns + other.columns, self.op)

  def groupby(self, attrs):
    # self.op = Grouping(attrs, self.op)
    # return self
    self.op = Grouping(attrs, self.op )
    return DataFrame2(self.columns,  self.op)

  def __getitem__(self, key):
    theType = type(key)

    if isinstance(key, Expr):
      # print(f"filter col: {key}")
      return self.filter(key)
    elif theType is str:
      # print(f"projection col: {key}")
      return self.project([key])
    elif theType is list:
      # print(f"projection list: {key}")
      return self.project(key)
    else:
      print(f"{key} has type {theType} -- ignoring")
      return self

#####################################################
### aggregates

  def min(self, col=None):
    return self._execAgg("min",col)

  def max(self, col=None):
    return self._execAgg("max",col)

  def mean(self, col=None):
    return self._execAgg('avg',col)

  def count(self, col=None):
    colName = "*"
    if col is not None:
      colName = col
    return self._execAgg("count",colName)

  def sum(self , col=None):
    return self._execAgg("sum", col)


  def _execAgg(self, func, col):
    """
    Actually compute the aggregation function.

    If we have a GROUP BY operation, the aggregation is only stored
    as a transformation and needs to be executed using show() or similar.

    If no grouping exists, we want to compute the aggregate over the complete
    table and return the scalar result directly
    """
    colName = None
    if col is None:
      colName = self.columns[0]
    else:
      colName = col

    funcCode = f"{func}({colName})"  

    if isinstance(self.op, Grouping):
      newOp = Grouping(self.op.groupcols, self.op.parent)
      newOp.setAggFunc(funcCode)
      
      return DataFrame2(self.columns, newOp)
      
    else:
      return self._doExecAgg(funcCode)
    

  def _doExecAgg(self, funcCode):
    """
    Really executes the aggregation and returns the single result
    """

    # aggregation over a table is performed in a way that the actual query
    # that was built is executed as an inner query and around that, we 
    # compute the aggregation
    innerSQL = self.sql()
    aggSQL = f"SELECT {funcCode} FROM ({innerSQL}) as t"
    
    # execute an SQL query and get the result set
    rs = self._doExecQuery(aggSQL)
    #fetch first (and only) row, return first column only
    return rs.scalar()


  def _doExecQuery(self, qry):
    """
    Execute an arbitrary SQL query and return the result set
    """
    with Connection.engine.connect() as con:
      rs = con.execute(qry)
      return rs

### produce SQL string
  def sql(self):
    """
    Produce a SQL string from the current operator tree
    """

    # the query object
    qry = query.Query()

    # traverse the "query plan" and fill the query object
    currOp = self.op
    while currOp != None:
      
      if isinstance(currOp, Filter):
        qry.filters.append(currOp)
      elif isinstance(currOp, Projection):
        qry.projList = currOp.attrs
        if currOp.distinct:
          qry.distinct = "distinct"
      elif isinstance(currOp, From):
        qry.froms= currOp.relation
      elif isinstance(currOp, Grouping):
        fqn = map(lambda x: f"{currOp.name()}.{x}", currOp.groupcols)
        qry.groupcols.extend(fqn)
        qry.groupagg = currOp.aggFunc
      elif isinstance(currOp, Join):
        qry.joins.append(currOp)

      currOp = currOp.parent

    # let the query object produce the actual SQL
    return qry.sql()

### Run query and print results
  def show(self):
    """
    Execute the operations and print results to stdout
    """

    qry = self.sql()

    print(qry)

    with Connection.engine.connect() as con:
      rs = con.execute(qry)

      for row in rs:
        print(row)

################
### comparisons
  def __eq__(self, other):
    # print(f"eq on {self.columns[0]} and {other}")
    expr = Eq(f"{self.op.name()}.{self.columns[0]}", other)
    return expr


  def __gt__(self, other):
    expr = Gt(f"{self.op.name()}.{self.columns[0]}", other)
    return expr

  def __lt__(self, other):
    expr = Lt(f"{self.op.name()}.{self.columns[0]}", other)
    return expr

  def __ge__(self, other):
    expr = Ge(f"{self.op.name()}.{self.columns[0]}", other)
    return expr
  
  def __le__(self, other):
    expr = Le(f"{self.op.name()}.{self.columns[0]}", other)
    return expr

  def __ne__(self, other):
    expr = Ne(f"{self.op.name()}.{self.columns[0]}", other)
    return expr