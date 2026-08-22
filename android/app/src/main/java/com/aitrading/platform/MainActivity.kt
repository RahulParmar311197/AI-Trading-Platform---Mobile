package com.aitrading.platform

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity: ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { TradingApp() } }
}

@Composable
fun TradingApp() {
    var tab by remember { mutableStateOf(0) }
    val tabs=listOf("Home","Markets","Scanner","AI","Replay","Backtest","Portfolio")
    Scaffold(bottomBar={ NavigationBar { tabs.forEachIndexed { i,t -> NavigationBarItem(selected=tab==i,onClick={tab=i},icon={},label={Text(t)}) } } }) { pad ->
        LazyColumn(modifier=Modifier.padding(pad).padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
            item { Text("AI Trading Platform", style=MaterialTheme.typography.headlineMedium) }
            item { Text("Deterministic risk controls remain authoritative.") }
            item { ElevatedCard { Column(Modifier.padding(16.dp)) { Text("Market Status"); Text("● NORMAL") } } }
            item { ElevatedCard { Column(Modifier.padding(16.dp)) { Text("Top Opportunities"); Text("NIFTY   87"); Text("BANKNIFTY   82"); Text("BTC/USDT   76") } } }
            item { ElevatedCard { Column(Modifier.padding(16.dp)) { Text("AI Trading"); Text("OFF") } } }
            item { when(tab) { 1 -> Text("Markets and live quotes"); 2 -> Text("Scanner: SMC / ICT / score filters"); 3 -> Text("AI analysis and strategy builder"); 4 -> Text("Replay: historical candle-by-candle simulation"); 5 -> Text("Backtest: strategy performance"); 6 -> Text("Portfolio, positions and P&L"); else -> Text("Analyze → Replay → Backtest → Paper → Live") } }
        }
    }
}
