// App.js
import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import ConnectScreen    from "./screens/ConnectScreen";
import ControllerScreen from "./screens/ControllerScreen";

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Stack.Navigator
        initialRouteName="Connect"
        screenOptions={{ headerShown: false, animation: "fade" }}>
        <Stack.Screen name="Connect"    component={ConnectScreen} />
        <Stack.Screen name="Controller" component={ControllerScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
