var mytree = function (selector,main_width,main_height,nodes,links) {

    var MARGIN=6;
    var RADIUS=2;

    var GRID=10;

    main_width=GRID*Math.floor(main_width/GRID);
    main_height=GRID*Math.floor(main_height/GRID);

    var svg = d3.select(selector); /*,
				     main_width = +svg.attr("width"),
				     main_height = +svg.attr("height");*/

    svg_defs=svg.append("defs");
    svg_defs.append("marker")
	.attr("id", "arrow")
	.attr("markerWidth", "10")
	.attr("markerHeight", "10")
	.attr("refX", "6.5")
	.attr("refY", "5")
	.attr("orient", "auto")
	.attr("markerUnits", "strokeWidth")
	.append("path")
	.attr("d","M0,0 L0,10 L8,5 z")
	.attr("fill","#000");

    svg.append("rect")
	.attr("x",0)
	.attr("y",0)
	.attr("width",main_width)
	.attr("height",main_height)
	.attr("fill","#fff")
	.attr("stroke","#000");

    var simulation = d3.forceSimulation()
	.force("link", d3.forceLink().id(function(d) { return d.id; }))
	.force("charge", d3.forceManyBody())
	.force("center", d3.forceCenter(main_width / 2, main_height / 2))
	.force('collide',d3.forceCollide(50));

    var link = svg.append("g")
	.attr("class", "links")
	.selectAll("line")
	.data(links)
	.enter().append("line")
	.attr("marker-end","url(#arrow)")
	.style("stroke", "#000")
	.style("stroke-width", "1px");

    var g_node = svg.append("g")
	.attr("class", "nodes")
	.selectAll("g.classnode")
	.data(nodes)
	.enter()
	.append("g")
	.attr("class", "classnode");

    var backnode=g_node.append("g");

    var labelnode=g_node.append("text")
	.attr("fill",function(d) { return d.color.fg; } )
    
    var labelnamenode=labelnode.append("tspan")
	.attr("x",0)
	.attr("dy","1.2em")
        .attr("text-anchor","middle")
	.text(function(d){return d.module;});

    var labelmodulenode=labelnode.append("tspan")
	.attr("x",0)
	.attr("dy","1.2em")
        .attr("text-anchor","middle")
	.text(function(d){return d.name;});

    labelnode
	.each(function(d) {
	    d.width = this.getBBox().width+2*MARGIN;
	    d.height = this.getBBox().height+2*MARGIN;
	    d.width = 2*GRID * Math.ceil( d.width/(2*GRID) );
	    d.height = 2*GRID * Math.ceil( d.height/(2*GRID) );
	});

    var node= backnode
	.append("rect")
	.attr("stroke",function(d) { return d.color.fg; } )
	.attr("fill",function(d) { return d.color.bg; } )
	.attr("width", function(d){ return d.width; })
	.attr("height", function(d){ return d.height; });

    var north= backnode
	.append("circle")
	.attr("fill","none")
	.attr("r", RADIUS);

    var west= backnode
	.append("circle")
	.attr("fill","none")
	.attr("r", RADIUS);

    var south= backnode
	.append("circle")
	.attr("fill","none")
	.attr("r", RADIUS);

    var east= backnode
	.append("circle")
	.attr("fill","none")
	.attr("r", RADIUS);

    node.call(d3.drag()
              .on("start", dragstarted)
              .on("drag", dragged)
              .on("end", dragended));


    simulation
	.nodes(nodes)
	.on("tick", ticked);

    simulation.force("link")
	.links(links);

    function calc_t(l) {
	var dquad;
	dquad=Math.pow(l.source.x-l.target.x,2)+Math.pow(l.source.y-l.target.y,2);
	return MARGIN/Math.sqrt(dquad); 
    };

    function calc_square_distance(A,B) {
	return Math.pow(A.x-B.x,2)+Math.pow(A.y-B.y,2);
    };

    function calc_module_distance(A,B) {
	return Math.abs(A.x-B.x,2)+Math.abs(A.y-B.y,2);
    };

    /** Choice of link anchors:

	  Q1 | north  | Q2
       ------+--------+------
        west |  RECT  | east
       ------+--------+------
          Q3 | south  | Q4

     **/

    function on_q1(center,north,west) {
	var d_north=calc_module_distance(center,north);
	var d_west=calc_module_distance(center,north);
	
	if (d_west<d_north) return west;
	return north;
    };

    function on_q2(center,north,east) {
	var d_north=calc_module_distance(center,north);
	var d_east=calc_module_distance(center,north);
	
	if (d_east<d_north) return east;
	return north;
    };

    function on_q3(center,south,west) {
	var d_south=calc_module_distance(center,south);
	var d_west=calc_module_distance(center,south);
	
	if (d_west<d_south) return west;
	return south;
    };

    function on_q4(center,south,east) {
	var d_south=calc_module_distance(center,south);
	var d_east=calc_module_distance(center,south);
	
	if (d_east<d_south) return east;
	return south;
    };

    function ticked() {

	node
            .each(function(d){
		d.x=GRID*Math.round(d.x/GRID);
		d.y=GRID*Math.round(d.y/GRID);

		d.x=Math.max( d.width/2, Math.min(main_width-d.width/2,d.x) ); 
		d.y=Math.max( d.height/2, Math.min(main_height-d.height/2,d.y) ); 

		d.north={"x": d.x, "y":d.y-d.height/2};
		d.south={"x": d.x, "y":d.y+d.height/2};
		d.east={"x": d.x+d.width/2, "y":d.y};
		d.west={"x": d.x-d.width/2, "y":d.y};
	    })
            .attr("x", function(d) { return d.x - d.width/2; })
            .attr("y", function(d) { return d.y - d.height/2; });

	north
            .attr("cx", function(d) { return d.north.x })
            .attr("cy", function(d) { return d.north.y });

	south
            .attr("cx", function(d) { return d.south.x })
            .attr("cy", function(d) { return d.south.y });

	west
            .attr("cx", function(d) { return d.west.x })
            .attr("cy", function(d) { return d.west.y });

	east
            .attr("cx", function(d) { return d.east.x })
            .attr("cy", function(d) { return d.east.y });

	labelnode
            .attr("x", function(d) { return d.x; })
            .attr("y", function(d) { return d.y - d.height/2 ; });

	labelnamenode
            .attr("x", function(d) { return d.x; })

	labelmodulenode
            .attr("x", function(d) { return d.x; })

	link
            .each( function(d){
		/*var S_anchors=[
		    d.source.north,
		    d.source.south,
		    d.source.west,
		    d.source.east
		];*/

		var T_anchors=[
		    d.target.north,
		    d.target.south,
		    d.target.west,
		    d.target.east
		];

		var t,dsquare;
		var min_dsquare=-1;
		var min_couple;

		//for(s=0;s<4;s++) {
		    for(t=0;t<4;t++) {
			dsquare=calc_module_distance(d.source,T_anchors[t]);
			if (min_dsquare==-1) {
			    min_dsquare=dsquare;
			    min_couple=[ d.source,T_anchors[t] ]
			    continue;
			}
			if (dsquare>=min_dsquare) continue;
			min_dsquare=dsquare;
			min_couple=[ d.source,T_anchors[t] ]
		    }
		//}

		d.vertex={
		    "x1": min_couple[0].x,
		    "y1": min_couple[0].y,
		    "x2": min_couple[1].x,
		    "y2": min_couple[1].y
		};
	    })
            .attr("x1", function(d) { 
		return d.vertex["x1"];
	    })
            .attr("y1", function(d) { 
		return d.vertex["y1"];
	    })
            .attr("x2", function(d) { 
		return d.vertex["x2"];
	    })
            .attr("y2", function(d) { 
		return d.vertex["y2"];
	    });

    }

    function dragstarted(d) {
	if (!d3.event.active) simulation.alphaTarget(0.3).restart();
	d.fx = d.x;
	d.fy = d.y;
    }

    function dragged(d) {
	d.fx = d3.event.x;
	d.fy = d3.event.y;
	d.fx=GRID*Math.round(d.fx/GRID);
	d.fy=GRID*Math.round(d.fy/GRID);
    }

    function dragended(d) {
	if (!d3.event.active) simulation.alphaTarget(0);
	//d.fx = null;
	//d.fy = null;
    }

};
