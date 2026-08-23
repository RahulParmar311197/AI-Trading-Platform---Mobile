from app.walk_forward import build_windows, run_walk_forward


def test_builds_rolling_windows():
    windows=build_windows(100,40,20,20)
    assert [(w.train_start,w.train_end,w.test_start,w.test_end) for w in windows]==[(0,40,40,60),(20,60,60,80),(40,80,80,100)]


def test_walk_forward_keeps_test_out_of_training():
    candles=list(range(100))
    result=run_walk_forward(candles,40,20,lambda train:{'best':max(train)},lambda test,p:{'net_pnl':float(test[-1]-p['best'])},20)
    assert result.aggregate['windows']==3
    assert result.windows[0]['train_end']==result.windows[0]['test_start']
