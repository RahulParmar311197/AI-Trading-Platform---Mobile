import React, { useState } from 'react';
import { SafeAreaView, ScrollView, Text, TextInput, TouchableOpacity, View, StyleSheet } from 'react-native';
import { aiIntelligenceApi } from '../services/aiIntelligenceApi';

export default function AiPerformanceScreen() {
  const [rawTrades, setRawTrades] = useState('[{"pnl":100},{"pnl":-50},{"pnl":25}]');
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function analyze() {
    setLoading(true); setError('');
    try { setReport(await aiIntelligenceApi.performance(JSON.parse(rawTrades))); }
    catch (err) { setError(err.message || 'Invalid trade JSON'); }
    finally { setLoading(false); }
  }

  return <SafeAreaView style={styles.container}><ScrollView contentContainerStyle={styles.content}>
    <Text style={styles.title}>AI Performance</Text>
    <Text style={styles.subtitle}>Deterministic metrics with advisory AI feedback</Text>
    <View style={styles.card}>
      <Text style={styles.heading}>Trade history JSON</Text>
      <TextInput multiline value={rawTrades} onChangeText={setRawTrades} style={styles.input} />
      <TouchableOpacity disabled={loading} onPress={analyze} style={styles.button}><Text style={styles.buttonText}>{loading ? 'Analyzing...' : 'Analyze Performance'}</Text></TouchableOpacity>
    </View>
    {error ? <Text style={styles.error}>{error}</Text> : null}
    {report ? <View style={styles.card}>
      <Text style={styles.heading}>Report</Text>
      <Text>Total trades: {report.total_trades}</Text><Text>Wins: {report.wins}</Text><Text>Losses: {report.losses}</Text>
      <Text>Win rate: {(report.win_rate * 100).toFixed(1)}%</Text><Text>Net P&L: {report.net_pnl}</Text><Text>Expectancy: {report.expectancy}</Text><Text>Max drawdown: {report.max_drawdown}</Text>
    </View> : null}
    <Text style={styles.disclaimer}>Analytics describe historical results. AI suggestions do not automatically change trading rules.</Text>
  </ScrollView></SafeAreaView>;
}
const styles = StyleSheet.create({ container:{flex:1}, content:{padding:20}, title:{fontSize:25,fontWeight:'800',marginBottom:5}, subtitle:{color:'#666',marginBottom:18}, card:{borderWidth:1,borderColor:'#ddd',borderRadius:14,padding:16,marginBottom:14}, heading:{fontSize:18,fontWeight:'700',marginBottom:10}, input:{borderWidth:1,borderColor:'#ccc',borderRadius:10,padding:12,minHeight:110,marginBottom:10}, button:{padding:13,borderRadius:10,backgroundColor:'#111'}, buttonText:{color:'#fff',textAlign:'center',fontWeight:'700'}, error:{color:'#b00020',marginBottom:12}, disclaimer:{color:'#666',fontSize:12,lineHeight:18,marginTop:8} });
