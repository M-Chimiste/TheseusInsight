"use client";
import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { format } from "date-fns";
import { CalendarIcon, ArrowUpDown, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useInfiniteQuery, InfiniteData } from "@tanstack/react-query";

interface Paper {
  id: number;
  title: string;
  abstract: string;
  score: number;
  date: string;
  url: string;
}

interface PapersResponse {
  papers: Paper[];
  nextPage: number | null;
}

type SortField = 'title' | 'score' | 'date';
type SortDirection = 'asc' | 'desc';

interface SortConfig {
  field: SortField;
  direction: SortDirection;
}

type QueryKey = ['papers', number, { from: Date | undefined; to: Date | undefined }, SortConfig, string];

export default function PapersPage() {
  const [scoreFilter, setScoreFilter] = useState<number>(0);
  const [dateRange, setDateRange] = useState<{
    from: Date | undefined;
    to: Date | undefined;
  }>({
    from: undefined,
    to: undefined,
  });
  const [sortConfig, setSortConfig] = useState<SortConfig>({ field: 'date', direction: 'desc' });
  const [searchQuery, setSearchQuery] = useState('');
  const [columnWidths, setColumnWidths] = useState<{ [key: string]: number }>({
    title: 300,
    abstract: 400,
    score: 100,
    date: 150,
  });
  const resizingRef = useRef<{ column: string | null; startX: number; startWidth: number }>({
    column: null,
    startX: 0,
    startWidth: 0,
  });

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
  } = useInfiniteQuery<PapersResponse, Error, InfiniteData<PapersResponse>, QueryKey, number>({
    queryKey: ['papers', scoreFilter, dateRange, sortConfig, searchQuery],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({
        page: pageParam.toString(),
        score: scoreFilter.toString(),
        sort_field: sortConfig.field,
        sort_direction: sortConfig.direction,
        search: searchQuery,
        ...(dateRange.from && { from: dateRange.from.toISOString() }),
        ...(dateRange.to && { to: dateRange.to.toISOString() }),
      });

      const response = await fetch(`/api/papers?${params}`);
      if (!response.ok) throw new Error('Failed to fetch papers');
      return response.json();
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.nextPage,
  });

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight - scrollTop <= clientHeight * 1.5) {
      if (hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    }
  };

  const handleSort = (field: SortField) => {
    setSortConfig((prev) => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const handleResizeStart = (e: React.MouseEvent, column: string) => {
    e.preventDefault();
    const th = e.currentTarget.parentElement as HTMLElement;
    resizingRef.current = {
      column,
      startX: e.pageX,
      startWidth: th.offsetWidth,
    };
    document.addEventListener('mousemove', handleResizeMove);
    document.addEventListener('mouseup', handleResizeEnd);
  };

  const handleResizeMove = (e: MouseEvent) => {
    if (!resizingRef.current.column) return;
    const diff = e.pageX - resizingRef.current.startX;
    setColumnWidths((prev) => ({
      ...prev,
      [resizingRef.current.column!]: Math.max(100, resizingRef.current.startWidth + diff),
    }));
  };

  const handleResizeEnd = () => {
    resizingRef.current.column = null;
    document.removeEventListener('mousemove', handleResizeMove);
    document.removeEventListener('mouseup', handleResizeEnd);
  };

  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleResizeMove);
      document.removeEventListener('mouseup', handleResizeEnd);
    };
  }, []);

  return (
    <div className="container mx-auto py-6">
      <h1 className="text-3xl font-bold mb-6">Paper Ratings</h1>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Filters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              <div className="space-y-2">
                <Label>Minimum Score</Label>
                <div className="flex items-center gap-4">
                  <Slider
                    value={[scoreFilter]}
                    onValueChange={([value]: number[]) => setScoreFilter(value)}
                    max={10}
                    step={0.1}
                    className="flex-1"
                  />
                  <span className="w-12 text-right">{scoreFilter.toFixed(1)}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>From Date</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !dateRange.from && "text-muted-foreground"
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateRange.from ? (
                          format(dateRange.from, "PPP")
                        ) : (
                          <span>Pick a date</span>
                        )}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <Calendar
                        mode="single"
                        selected={dateRange.from}
                        onSelect={(date: Date | undefined) =>
                          setDateRange((prev) => ({ ...prev, from: date }))
                        }
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>

                <div className="space-y-2">
                  <Label>To Date</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !dateRange.to && "text-muted-foreground"
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateRange.to ? (
                          format(dateRange.to, "PPP")
                        ) : (
                          <span>Pick a date</span>
                        )}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <Calendar
                        mode="single"
                        selected={dateRange.to}
                        onSelect={(date: Date | undefined) =>
                          setDateRange((prev) => ({ ...prev, to: date }))
                        }
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search titles and abstracts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="max-w-sm"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            <div className="h-[600px] overflow-auto" onScroll={handleScroll}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead
                      style={{ width: columnWidths.title }}
                      className="relative"
                    >
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          onClick={() => handleSort('title')}
                          className="h-8 px-2"
                        >
                          Title
                          <ArrowUpDown className="ml-2 h-4 w-4" />
                        </Button>
                        <div
                          className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary"
                          onMouseDown={(e) => handleResizeStart(e, 'title')}
                        />
                      </div>
                    </TableHead>
                    <TableHead
                      style={{ width: columnWidths.abstract }}
                      className="relative"
                    >
                      <div className="flex items-center gap-2">
                        <span>Abstract</span>
                        <div
                          className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary"
                          onMouseDown={(e) => handleResizeStart(e, 'abstract')}
                        />
                      </div>
                    </TableHead>
                    <TableHead
                      style={{ width: columnWidths.score }}
                      className="relative"
                    >
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          onClick={() => handleSort('score')}
                          className="h-8 px-2"
                        >
                          Score
                          <ArrowUpDown className="ml-2 h-4 w-4" />
                        </Button>
                        <div
                          className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary"
                          onMouseDown={(e) => handleResizeStart(e, 'score')}
                        />
                      </div>
                    </TableHead>
                    <TableHead
                      style={{ width: columnWidths.date }}
                      className="relative"
                    >
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          onClick={() => handleSort('date')}
                          className="h-8 px-2"
                        >
                          Date
                          <ArrowUpDown className="ml-2 h-4 w-4" />
                        </Button>
                        <div
                          className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary"
                          onMouseDown={(e) => handleResizeStart(e, 'date')}
                        />
                      </div>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {status === 'pending' ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center">
                        Loading...
                      </TableCell>
                    </TableRow>
                  ) : status === 'error' ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-red-500">
                        Error loading papers
                      </TableCell>
                    </TableRow>
                  ) : (
                    data?.pages.map((page) =>
                      page.papers.map((paper: Paper) => (
                        <TableRow key={paper.id}>
                          <TableCell>
                            <a
                              href={paper.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:underline"
                            >
                              {paper.title}
                            </a>
                          </TableCell>
                          <TableCell>
                            <div className="max-w-md truncate" title={paper.abstract}>
                              {paper.abstract}
                            </div>
                          </TableCell>
                          <TableCell>{paper.score.toFixed(1)}</TableCell>
                          <TableCell>{format(new Date(paper.date), 'PPP')}</TableCell>
                        </TableRow>
                      ))
                    )
                  )}
                </TableBody>
              </Table>
              {isFetchingNextPage && (
                <div className="text-center py-4">Loading more...</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 