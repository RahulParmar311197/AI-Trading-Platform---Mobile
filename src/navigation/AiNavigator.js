import React, { useState } from 'react';
import { SafeAreaView, Text, TouchableOpacity, View, StyleSheet } from 'react-native';
import AiDashboardScreen from '../screens/AiDashboardScreen';
import AiPerformanceScreen from '../screens/AiPerformanceScreen';

const screens = { Dashboard: AiDashboardScreen, Performance: AiPerformanceScreen };

export default function AiNavigator() {
  const [route, setRoute] = useState('Dashboard');
  const Screen = screens[route];
  return <SafeAreaView style={styles.root}>
    <View style={styles.nav}>{Object.keys(screens).map(name => <TouchableOpacity key={name} onPress={() => setRoute(name)} style={[styles.tab, route === name && styles.active]}><Text style={styles.tabText}>{name}</Text></TouchableOpacity>)}</View>
    <View style={styles.screen}><Screen /></View>
  </SafeAreaView>;
}
const styles = StyleSheet.create({root:{flex:1},screen:{flex:1},nav:{flexDirection:'row',borderBottomWidth:1,borderBottomColor:'#ddd'},tab:{flex:1,padding:14,alignItems:'center'},active:{borderBottomWidth:2,borderBottomColor:'#111'},tabText:{fontWeight:'700'}});
