import React, { useState } from 'react';
import { SafeAreaView, ScrollView, Text, TextInput, TouchableOpacity, View, StyleSheet } from 'react-native';
import { aiIntelligenceApi } from '../services/aiIntelligenceApi';

export default function AiDashboardScreen() {
  const [question, setQuestion] = useState('');
  const [strategyPrompt, setStrategyPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function runResearch() {
    setLoading(true); setError('');
    try {
      const data = await aiIntelligenceApi.research(question, { facts: [] });
      setResult(data);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  async function buildStrategy() {
    setLoading(true); setError('');
    try {
      const data = await aiIntelligenceApi.strategy(strategyPrompt, false);
      setResult({ answer: JSON.stringify(data.strategy, null, 2), evidence: [] });
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>AI Trading Intelligence</Text>
        <Text style={styles.subtitle}>Grounded analysis • deterministic trading authority</Text>

        <View style={styles.card}>
          <Text style={styles.heading}>Research</Text>
          <TextInput value={question} onChangeText={setQuestion} placeholder="Ask about the supplied evidence" style={styles.input} />
          <TouchableOpacity disabled={loading || question.length < 3} onPress={runResearch} style={styles.button}>
            <Text style={styles.buttonText}>{loading ? 'Working…' : 'Research'}</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.card}>
          <Text style={styles.heading}>Strategy Builder</Text>
          <TextInput value={strategyPrompt} onChangeText={setStrategyPrompt} placeholder="Describe your strategy" style={styles.input} />
          <TouchableOpacity disabled={loading || strategyPrompt.length < 3} onPress={buildStrategy} style={styles.button}>
            <Text style={styles.buttonText}>Build Strategy</Text>
          </TouchableOpacity>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}
        {result ? (
          <View style={styles.card}>
            <Text style={styles.heading}>AI Result</Text>
            <Text style={styles.result}>{result.answer || JSON.stringify(result, null, 2)}</Text>
            {result.evidence?.length ? <Text style={styles.evidence}>Evidence: {result.evidence.join(' • ')}</Text> : null}
          </View>
        ) : null}

        <Text style={styles.disclaimer}>AI explains evidence and builds candidates; it does not place orders or override deterministic risk controls.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: 20 },
  title: { fontSize: 25, fontWeight: '800', marginBottom: 5 },
  subtitle: { color: '#666', marginBottom: 18 },
  card: { borderWidth: 1, borderColor: '#ddd', borderRadius: 14, padding: 16, marginBottom: 14 },
  heading: { fontSize: 18, fontWeight: '700', marginBottom: 10 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 10, padding: 12, marginBottom: 10 },
  button: { padding: 13, borderRadius: 10, backgroundColor: '#111' },
  buttonText: { color: '#fff', textAlign: 'center', fontWeight: '700' },
  result: { fontSize: 14, lineHeight: 20 },
  evidence: { marginTop: 12, color: '#555' },
  error: { color: '#b00020', marginBottom: 12 },
  disclaimer: { color: '#666', fontSize: 12, lineHeight: 18, marginTop: 8 },
});
