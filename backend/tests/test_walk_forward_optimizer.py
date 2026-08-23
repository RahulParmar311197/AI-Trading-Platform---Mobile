from app.walk_forward_optimizer import optimize_walk_forward


def test_optimizer_uses_train_and_evaluates_oos():
    candles=list(range(20))
    def train_eval(data,p): return {'net_pnl':p['x']*len(data),'max_drawdown':0.05}
    def test_eval(data,p): return {'net_pnl':p['x']*len(data)}
    result=optimize_walk_forward(candles,train_size=10,test_size=5,parameter_grid={'x':[1,2]},train_evaluator=train_eval,test_evaluator=test_eval)
    assert result.aggregate['windows']==2
    assert all(row['parameters']=={'x':2} for row in result.windows)
    assert result.aggregate['oos_net_pnl']==20
