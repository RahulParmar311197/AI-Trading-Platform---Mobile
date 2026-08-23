from app.parameter_optimizer import grid_search, best_parameters


def test_grid_search_ranks_and_filters():
    grid={'threshold':[50,70,90],'rr':[1,2]}
    def evaluate(p):
        return {'net_pnl':p['threshold']*p['rr'],'max_drawdown':0.1 if p['rr']==2 else 0.05}
    results=grid_search(grid,evaluate,objective='net_pnl',max_drawdown_limit=0.1)
    assert len(results)==6
    assert results[0].parameters=={'threshold':90,'rr':2}
    assert best_parameters(results)==results[0].parameters


def test_drawdown_constraint():
    results=grid_search({'x':[1,2]},lambda p:{'net_pnl':p['x'],'max_drawdown':0.2 if p['x']==2 else 0.05},max_drawdown_limit=0.1)
    assert len(results)==1
    assert results[0].parameters=={'x':1}
