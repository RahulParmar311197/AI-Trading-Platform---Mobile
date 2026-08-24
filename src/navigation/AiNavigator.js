import React, { useState } from 'react';
import { SafeAreaView, Text, TouchableOpacity, View, StyleSheet } from 'react-native';
import AiDashboardScreen from '../screens/AiDashboardScreen';
import AiPerformanceScreen from '../screens/AiPerformanceScreen';
import AiTradeExplanationScreen from '../screens/AiTradeExplanationScreen';
import BrokerAccountsScreen from '../screens/BrokerAccountsScreen';

const screens = { Dashboard: AiDashboardScreen, Performance: AiPerformanceScreen, 'Trade Explain': AiTradeExplanationScreen, Brokers: BrokerAccountsScreen };

export default function AiNavigator({ onLogout }) {
  const [route, setRoute] = useState('Dashboard');
  const Screen = screens[route];
  return <SafeAreaView style={styles.root}>
    <View style={styles.nav}>{Object.keys(screens).map(name => <TouchableOpacity key={name} onPress={() => setRoute(name)} style={[styles.tab, route === name && styles.active]}><Text style={styles.tabText}>{name}</Text></TouchableOpacity>)}</View>
    <View style={styles.screen}><Screen /></View>
    <TouchableOpacity onPress={onLogout} style={styles.logout}><Text style={styles.logoutText}>Logout</Text></TouchableOpacity>
  </SafeAreaView>;
}
const styles = StyleSheet.create({root:{flex:1},screen:{flex:1},nav:{flexDirection:'row',borderBottomWidth:1,borderBottomColor:'#ddd'},tab:{flex:1,padding:12,alignItems:'center'},active:{borderBottomWidth:2,borderBottomColor:'#111'},tabText:{fontWeight:'700',fontSize:12},logout:{padding:12,alignItems:'center',borderTopWidth:1,borderTopColor:'#ddd'},logoutText:{fontWeight:'700'}});
