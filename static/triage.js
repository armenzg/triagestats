/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const SEVERITIES = ["blocker+critical+major", "normal", "minor+trivial"];
const COLORS = {"blocker+critical+major": "rgb(255, 99, 132)",
                "normal": "rgb(54, 162, 235)",
                "minor+trivial": "rgb(75, 192, 192)"};

function makeChart(canvasId, labels, component, info) {
  window.addEventListener("DOMContentLoaded", function() {
    const color = Chart.helpers.color;
    const chartData = {
      labels: labels,
      datasets: []
    };
    
    for (const sev of SEVERITIES) {
      const c = color(COLORS[sev]).alpha(0.5).rgbString();
      const ds = {
        label: sev,
        fill: false,
        backgroundColor: c,
        borderColor: c,
        data: info[sev]
      };
      chartData.datasets.push(ds);
    }

    const ctx = document.getElementById(canvasId).getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: chartData,
      options: {
        legend: {
		  position: "top",
	    },
	    title: {
		  display: true,
		  text: component
	    }
      }
    });
  });
}

function makeTeam(team, teamUl) {
  for (const person of team) {
    const name = person[0];
    const t = person[1];
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.setAttribute("href", name + ".html");
    a.innerText = name;
    li.append(a);
    teamUl.append(li);
    if (t.length == 0) {
      li.setAttribute("class", "dropdown-item");
    } else {
      li.setAttribute("class", "dropdown-submenu");
      a.setAttribute("class", "dropdown-item");
      const ul = document.createElement("ul");
      ul.setAttribute("class", "dropdown-menu");
      li.append(ul);
      makeTeam(t, ul);
    }
  }
}

function createTeam(team, teamId) {
  const ul = document.getElementById(teamId);
  if (!ul) {
    return;
  }
  makeTeam(team[1], ul);  
}

window.addEventListener("load", function() {
  createTeam(personTeam, "team");
  createTeam(managerTeam, "manager-team");
});

